import { useEffect, useRef, useState, type ComponentType } from 'react';
import { Book } from './components/Book/Book';
import { CONTENT_ID, PortfolioShell } from './components/PortfolioShell/PortfolioShell';
import { useSection } from './hooks/useSection';
import { AboutPage } from './pages/AboutPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { SkillsPage } from './pages/SkillsPage';
import { DEFAULT_SECTION, SECTION_BY_ID, type SectionId } from './sections';
import styles from './App.module.css';

const SITE_TITLE = 'Seoyeon Cho | Software Engineer';

const PAGES: Record<SectionId, ComponentType> = {
  about: AboutPage,
  projects: ProjectsPage,
  skills: SkillsPage,
};

export default function App() {
  const section = useSection();
  const [announcement, setAnnouncement] = useState('');
  const firstRender = useRef(true);
  const Page = PAGES[section];
  const { label } = SECTION_BY_ID[section];

  useEffect(() => {
    document.title = section === DEFAULT_SECTION ? SITE_TITLE : `${label} | Seoyeon Cho`;
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    setAnnouncement(`${label} page`);
  }, [section, label]);

  return (
    <PortfolioShell announcement={announcement}>
      <Book section={section} />
      <main id={CONTENT_ID} className={styles.main} tabIndex={-1}>
        <Page key={section} />
      </main>
    </PortfolioShell>
  );
}
