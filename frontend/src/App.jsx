import { useState } from 'react';
import MatchHistory from './views/MatchHistory.jsx';
import HeroStats from './views/HeroStats.jsx';
import TalentBuilds from './views/TalentBuilds.jsx';
import Matchups from './views/Matchups.jsx';
import Groups from './views/Groups.jsx';

const TABS = {
  matches: { label: 'Match History', view: MatchHistory },
  heroes: { label: 'Hero Stats', view: HeroStats },
  talents: { label: 'Talent Builds', view: TalentBuilds },
  matchups: { label: 'Matchups', view: Matchups },
  groups: { label: 'Friends & Groups', view: Groups },
};

export default function App() {
  const [tab, setTab] = useState('matches');
  const View = TABS[tab].view;

  return (
    <div className="app">
      <header className="app__header">
        <h1>Heroes Tracker</h1>
        <nav className="tabs">
          {Object.entries(TABS).map(([key, t]) => (
            <button
              key={key}
              className={key === tab ? 'tab tab--active' : 'tab'}
              onClick={() => setTab(key)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main className="app__main">
        <View />
      </main>
    </div>
  );
}
