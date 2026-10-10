import {
  Box3,
  DirectionalLight,
  HemisphereLight,
  MathUtils,
  Mesh,
  MeshPhysicalMaterial,
  MeshStandardMaterial,
  NeutralToneMapping,
  Object3D,
  PCFShadowMap,
  PerspectiveCamera,
  PlaneGeometry,
  PMREMGenerator,
  Quaternion,
  Scene,
  ShadowMaterial,
  Vector3,
  WebGLRenderer,
  type Texture,
} from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { isSectionId, SECTION_IDS, type SectionId } from '../sections';
import type { BookMeta, BookView, Quad, TabQuads, ViewId } from './types';

export interface BookStageHandlers {
  /** Called after every rendered frame with each tab's label face in stage pixels. */
  onQuads(quads: TabQuads): void;
  onContextLost(): void;
}

export interface BookStageInit {
  canvas: HTMLCanvasElement;
  modelUrl: string;
  meta: BookMeta;
  view: ViewId;
  section: SectionId;
  reducedMotion: boolean;
  width: number;
  height: number;
  handlers: BookStageHandlers;
}

/** How far a tab rises out of the book, in scene units. */
const LIFT = { hover: 0.05, active: 0.15, pressed: -0.03 };
/** Slightly under-damped, so a tab settles with a small overshoot like stiff card. */
const SPRING = { stiffness: 260, damping: 21 };
/** Largest camera swing from pointer position, in radians. */
const PARALLAX = { yaw: 0.07, pitch: 0.03 };
/** The book turns a touch toward the open section. */
const SECTION_YAW: Record<SectionId, number> = { about: 0.03, projects: 0, skills: -0.03 };
const CAMERA_EASE = 6;
/** Half-width of the area the key light's shadow map covers, in scene units. */
const SHADOW_REACH = 7;
const MAX_PIXEL_RATIO = 2;
const NACRE_FILM: Record<SectionId, [number, number]> = {
  about: [320, 520],
  projects: [280, 460],
  skills: [360, 560],
};

interface TabRig {
  node: Object3D;
  restY: number;
  /** Label face corners in the tab's local space: TL, TR, BR, BL. */
  corners: [Vector3, Vector3, Vector3, Vector3];
  lift: number;
  velocity: number;
}

const UP = new Vector3(0, 1, 0);
const scratch = new Vector3();
const yawTurn = new Quaternion();
const pitchTurn = new Quaternion();
const turn = new Quaternion();
const rightAxis = new Vector3();

/**
 * The 3D book. Owns the renderer, scene, and camera; knows nothing about React.
 * It renders only while something is moving, then goes idle.
 */
export class BookStage {
  static async create(init: BookStageInit): Promise<BookStage> {
    const stage = new BookStage(init);
    try {
      const gltf = await new GLTFLoader().loadAsync(init.modelUrl);
      if (stage.disposed) return stage;
      stage.build(gltf.scene);
    } catch (error) {
      stage.dispose();
      throw error;
    }
    return stage;
  }

  private readonly renderer: WebGLRenderer;
  private readonly scene = new Scene();
  private readonly camera = new PerspectiveCamera(22, 1, 1, 80);
  private readonly handlers: BookStageHandlers;
  private readonly meta: BookMeta;
  private readonly canvas: HTMLCanvasElement;
  private readonly tabs = new Map<SectionId, TabRig>();
  private readonly props: { node: Object3D; box: Box3 }[] = [];
  private environment: Texture | null = null;

  private view: ViewId;
  private section: SectionId;
  private hovered: SectionId | null = null;
  private pressed: SectionId | null = null;
  private reducedMotion: boolean;
  private width: number;
  private height: number;

  private readonly baseOffset = new Vector3();
  private readonly baseQuaternion = new Quaternion();
  private readonly pivot = new Vector3();
  private pointerX = 0;
  private pointerY = 0;
  private yaw = 0;
  private pitch = 0;

  private frame = 0;
  private lastTime = 0;
  private built = false;
  private disposed = false;

  private constructor(init: BookStageInit) {
    this.canvas = init.canvas;
    this.handlers = init.handlers;
    this.meta = init.meta;
    this.view = init.view;
    this.section = init.section;
    this.reducedMotion = init.reducedMotion;
    this.width = init.width;
    this.height = init.height;

    this.renderer = new WebGLRenderer({ canvas: init.canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.toneMapping = NeutralToneMapping;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = PCFShadowMap;
    this.canvas.addEventListener('webglcontextlost', this.handleContextLost);
  }

  setSection(section: SectionId): void {
    if (section === this.section) return;
    this.section = section;
    this.invalidate();
  }

  setHover(section: SectionId | null): void {
    if (section === this.hovered) return;
    this.hovered = section;
    this.invalidate();
  }

  setPressed(section: SectionId | null): void {
    if (section === this.pressed) return;
    this.pressed = section;
    this.invalidate();
  }

  /** Pointer position across the viewport, each axis from -1 to 1. */
  setPointer(x: number, y: number): void {
    this.pointerX = MathUtils.clamp(x, -1, 1);
    this.pointerY = MathUtils.clamp(y, -1, 1);
    this.invalidate();
  }

  setView(view: ViewId): void {
    if (view === this.view) return;
    this.view = view;
    this.applyView();
    this.invalidate();
  }

  setReducedMotion(reduced: boolean): void {
    if (reduced === this.reducedMotion) return;
    this.reducedMotion = reduced;
    this.invalidate();
  }

  resize(width: number, height: number): void {
    if (width === this.width && height === this.height) return;
    this.width = width;
    this.height = height;
    this.applyView();
    this.invalidate();
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    cancelAnimationFrame(this.frame);
    this.canvas.removeEventListener('webglcontextlost', this.handleContextLost);
    this.scene.traverse((object) => {
      if (object instanceof Mesh) {
        object.geometry.dispose();
        for (const material of Array.isArray(object.material) ? object.material : [object.material]) material.dispose();
      }
    });
    this.environment?.dispose();
    this.renderer.dispose();
    this.renderer.forceContextLoss();
  }

  private handleContextLost = (event: Event): void => {
    event.preventDefault();
    if (!this.disposed) this.handlers.onContextLost();
  };

  private build(model: Object3D): void {
    const { scene, renderer } = this;

    const pmrem = new PMREMGenerator(renderer);
    this.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();
    scene.environment = this.environment;
    scene.environmentIntensity = 0.3;
    scene.add(new HemisphereLight(0xf0f4ff, 0xfbeedd, 1.15));

    model.traverse((object) => {
      if (object instanceof DirectionalLight) {
        // Strength and the shadow switch are authored on the light in Blender and exported as extras.
        const { strength, shadow } = object.userData as { strength?: number; shadow?: boolean | number };
        if (typeof strength === 'number') object.intensity = strength;
        if (shadow ?? object.name.startsWith('Light_Key')) {
          const { camera: frustum } = object.shadow;
          object.castShadow = true;
          object.shadow.mapSize.set(2048, 2048);
          frustum.left = -SHADOW_REACH;
          frustum.right = SHADOW_REACH;
          frustum.top = SHADOW_REACH;
          frustum.bottom = -SHADOW_REACH;
          frustum.near = 1;
          frustum.far = 40;
          frustum.updateProjectionMatrix();
          object.shadow.bias = -0.0004;
          object.shadow.normalBias = 0.02;
          object.shadow.radius = 5;
        }
      } else if (object instanceof Mesh) {
        object.castShadow = true;
        object.receiveShadow = true;
      }
    });

    for (const child of model.children) {
      if (child.name.startsWith('Tab_')) this.rigTab(child);
      else if (child.name.startsWith('Prop_')) this.props.push({ node: child, box: new Box3() });
    }
    scene.add(model);
    scene.updateMatrixWorld(true);
    for (const prop of this.props) prop.box.setFromObject(prop.node);

    const ground = new Mesh(new PlaneGeometry(80, 80), new ShadowMaterial({ color: 0x3a2f26, opacity: 0.2 }));
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    this.built = true;
    this.applyView();
    this.settle();
    this.render();
  }

  private rigTab(node: Object3D): void {
    const tagged = typeof node.userData.section === 'string' ? node.userData.section : node.name.slice(4).toLowerCase();
    if (!isSectionId(tagged)) return;

    let mesh: Mesh | null = null;
    node.traverse((object) => {
      if (!mesh && object instanceof Mesh) mesh = object;
    });
    if (!mesh) return;
    const tabMesh = mesh as Mesh;

    tabMesh.geometry.computeBoundingBox();
    const box = tabMesh.geometry.boundingBox!.clone();
    if (tabMesh !== node) box.applyMatrix4(tabMesh.matrix);

    const source = tabMesh.material as MeshStandardMaterial;
    tabMesh.material = new MeshPhysicalMaterial({
      color: source.color,
      roughness: 0.36,
      clearcoat: 0.5,
      clearcoatRoughness: 0.25,
      iridescence: 1,
      iridescenceIOR: 1.45,
      iridescenceThicknessRange: NACRE_FILM[tagged],
    });
    source.dispose();

    // The tab's origin sits on the page top edge, so y = 0 is the bottom of the visible face.
    const { min, max } = box;
    this.tabs.set(tagged, {
      node,
      restY: node.position.y,
      corners: [
        new Vector3(min.x, max.y, max.z),
        new Vector3(max.x, max.y, max.z),
        new Vector3(max.x, 0, max.z),
        new Vector3(min.x, 0, max.z),
      ],
      lift: 0,
      velocity: 0,
    });
  }

  private get viewDef(): BookView {
    return this.meta.views[this.view];
  }

  /** Camera, projection, and canvas size for the current view and stage box. */
  private applyView(): void {
    const view = this.viewDef;
    const { camera, renderer } = this;
    const width = Math.max(1, this.width);
    const height = Math.max(1, this.height);

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, MAX_PIXEL_RATIO));
    renderer.setSize(width, height, false);

    // Keep the safe area on screen: fill the height, or widen the lens when the stage is too narrow.
    const aspect = width / height;
    const widen = aspect >= view.safeAspect ? 1 : view.safeAspect / aspect;
    camera.fov = MathUtils.radToDeg(2 * Math.atan(Math.tan(MathUtils.degToRad(view.fovY) / 2) * widen));
    camera.aspect = aspect;
    camera.updateProjectionMatrix();

    this.pivot.fromArray(view.pivot);
    this.baseOffset.fromArray(view.position).sub(this.pivot);
    this.baseQuaternion.fromArray(view.quaternion);

    if (!this.built) return;
    this.placeCamera(0, 0);
    camera.updateMatrixWorld();
    for (const prop of this.props) prop.node.visible = this.fitsOnScreen(prop.box);
    this.placeCamera(this.yaw, this.pitch);
  }

  /** Side props are shown only when the whole piece is inside the frame. */
  private fitsOnScreen(box: Box3): boolean {
    for (let i = 0; i < 8; i++) {
      scratch.set(i & 1 ? box.max.x : box.min.x, i & 2 ? box.max.y : box.min.y, i & 4 ? box.max.z : box.min.z);
      scratch.project(this.camera);
      if (Math.abs(scratch.x) > 0.97 || Math.abs(scratch.y) > 0.99) return false;
    }
    return true;
  }

  private placeCamera(yaw: number, pitch: number): void {
    yawTurn.setFromAxisAngle(UP, yaw);
    rightAxis.set(1, 0, 0).applyQuaternion(this.baseQuaternion).applyQuaternion(yawTurn);
    pitchTurn.setFromAxisAngle(rightAxis, pitch);
    turn.copy(pitchTurn).multiply(yawTurn);
    this.camera.position.copy(this.baseOffset).applyQuaternion(turn).add(this.pivot);
    this.camera.quaternion.copy(turn).multiply(this.baseQuaternion);
  }

  private liftTarget(section: SectionId): number {
    let target = section === this.section ? LIFT.active : 0;
    if (section === this.hovered && section !== this.section) target += LIFT.hover;
    if (section === this.pressed) target += LIFT.pressed;
    return target;
  }

  private cameraTarget(): { yaw: number; pitch: number } {
    if (this.reducedMotion) return { yaw: 0, pitch: 0 };
    return {
      yaw: this.pointerX * PARALLAX.yaw + SECTION_YAW[this.section],
      pitch: this.pointerY * PARALLAX.pitch,
    };
  }

  /** Jump every animated value to its target, with no motion. */
  private settle(): void {
    for (const [section, rig] of this.tabs) {
      rig.lift = this.liftTarget(section);
      rig.velocity = 0;
    }
    const target = this.cameraTarget();
    this.yaw = target.yaw;
    this.pitch = target.pitch;
  }

  private invalidate(): void {
    if (this.frame || this.disposed || !this.built) return;
    this.lastTime = performance.now();
    this.frame = requestAnimationFrame(this.tick);
  }

  private tick = (now: number): void => {
    this.frame = 0;
    if (this.disposed) return;
    const dt = Math.min((now - this.lastTime) / 1000, 1 / 30);
    this.lastTime = now;
    let moving = false;

    if (this.reducedMotion) {
      this.settle();
    } else {
      for (const [section, rig] of this.tabs) {
        const target = this.liftTarget(section);
        // Two half steps keep the spring stable at low frame rates.
        for (let step = 0; step < 2; step++) {
          const half = dt / 2;
          rig.velocity += (SPRING.stiffness * (target - rig.lift) - SPRING.damping * rig.velocity) * half;
          rig.lift += rig.velocity * half;
        }
        if (Math.abs(target - rig.lift) > 0.0004 || Math.abs(rig.velocity) > 0.004) moving = true;
        else {
          rig.lift = target;
          rig.velocity = 0;
        }
      }
      const target = this.cameraTarget();
      const ease = 1 - Math.exp(-dt * CAMERA_EASE);
      this.yaw += (target.yaw - this.yaw) * ease;
      this.pitch += (target.pitch - this.pitch) * ease;
      if (Math.abs(target.yaw - this.yaw) > 0.0002 || Math.abs(target.pitch - this.pitch) > 0.0002) moving = true;
    }

    this.render();
    if (moving) this.frame = requestAnimationFrame(this.tick);
  };

  private render(): void {
    for (const rig of this.tabs.values()) rig.node.position.y = rig.restY + rig.lift;
    this.placeCamera(this.yaw, this.pitch);
    this.renderer.render(this.scene, this.camera);
    this.handlers.onQuads(this.measureTabs());
  }

  private measureTabs(): TabQuads {
    const quads = {} as Record<SectionId, Quad>;
    for (const section of SECTION_IDS) {
      const rig = this.tabs.get(section);
      if (!rig) continue;
      quads[section] = rig.corners.map((corner) => {
        scratch.copy(corner);
        rig.node.localToWorld(scratch).project(this.camera);
        return [(scratch.x * 0.5 + 0.5) * this.width, (-scratch.y * 0.5 + 0.5) * this.height] as const;
      }) as unknown as Quad;
    }
    return quads;
  }
}
