/** The three bookmarks. Order here is the order on the book and in the tab sequence. */
export const SECTION_IDS = ['about', 'projects', 'skills'] as const;

export type SectionId = (typeof SECTION_IDS)[number];
export type SectionHue = 'rose' | 'gold' | 'blue';

export interface Section {
  id: SectionId;
  label: string;
  /** Nacre hue shared by the 3D tab and the page marker. */
  hue: SectionHue;
}

export const SECTIONS: readonly Section[] = [
  { id: 'about', label: 'About', hue: 'rose' },
  { id: 'projects', label: 'Projects', hue: 'gold' },
  { id: 'skills', label: 'Skills', hue: 'blue' },
];

export const DEFAULT_SECTION: SectionId = 'about';

export const SECTION_BY_ID = Object.fromEntries(SECTIONS.map((section) => [section.id, section])) as Record<
  SectionId,
  Section
>;

export function isSectionId(value: string): value is SectionId {
  return (SECTION_IDS as readonly string[]).includes(value);
}

export function sectionHref(id: SectionId): string {
  return `#${id}`;
}
