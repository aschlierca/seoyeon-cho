import { useSyncExternalStore } from 'react';
import { DEFAULT_SECTION, isSectionId, type SectionId } from '../sections';

function readSection(): SectionId {
  const first = window.location.hash.replace(/^#\/?/, '').split('/')[0] ?? '';
  return isSectionId(first) ? first : DEFAULT_SECTION;
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener('hashchange', onChange);
  return () => window.removeEventListener('hashchange', onChange);
}

/** The active section, read from the URL hash so refresh, back, and shared links all work. */
export function useSection(): SectionId {
  return useSyncExternalStore(subscribe, readSection, () => DEFAULT_SECTION);
}
