# Seoyeon's Portfolio Website

A portfolio you open like a book. The book is a 3D model with three bookmarks, About, Projects, and Skills, that work as the site's navigation.

Built with React, TypeScript, Vite, and three.js. The book is modeled in Blender.

## Run it

```bash
npm install
npm run dev        # start the dev server
npm run build      # type-check and build to dist/
npm run preview    # serve the build
```

## Edit the book

`blender/book.blend` is the source for the 3D book. Open it in Blender, change what you like, save, then export:

```bash
npm run asset:export        # model, camera data, and still images (about 2 minutes)
npm run asset:export:fast   # model and camera data only (a few seconds)
```

The export writes `public/models/book.glb`, `public/posters/`, and `src/stage/bookMeta.json`. Do not edit those by hand.

A few names matter to the site: the three bookmarks are `Tab_About`, `Tab_Projects`, and `Tab_Skills`, and the two cameras are `Camera_Desktop` and `Camera_Mobile`. Keep those names.

`npm run asset:build` creates `book.blend` from `blender/build_book.py` the first time only. It will not overwrite an existing file unless you pass `-- --force`, which backs the current file up first.

Blender is found automatically on macOS. Elsewhere, set `BLENDER_BIN` to the Blender executable.

## Fonts

Wanted Sans by Wanted Lab, SIL Open Font License 1.1.
