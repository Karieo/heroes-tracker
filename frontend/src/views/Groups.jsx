import { useEffect, useState } from 'react';
import { api } from '../api';

export default function Groups() {
  const [players, setPlayers] = useState([]);
  const [groups, setGroups] = useState([]);
  const [newTag, setNewTag] = useState('');
  const [newName, setNewName] = useState('');
  const [error, setError] = useState('');

  function refresh() {
    api.listPlayers(true).then(setPlayers).catch((e) => setError(e.message));
    api.groups(1).then(setGroups).catch((e) => setError(e.message));
  }

  useEffect(refresh, []);

  async function addPlayer(e) {
    e.preventDefault();
    if (!newTag.includes('#')) {
      setError('Battletag must look like Name#1234');
      return;
    }
    try {
      await api.addPlayer(newTag.trim(), newName.trim() || undefined);
      setNewTag('');
      setNewName('');
      setError('');
      refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleActive(p) {
    await api.updatePlayer(p.id, { active: p.active ? 0 : 1 });
    refresh();
  }

  async function remove(p) {
    if (!confirm(`Remove ${p.display_name} (${p.battletag}) from the roster?`)) return;
    await api.deletePlayer(p.id);
    refresh();
  }

  return (
    <section>
      <h2>Friends & Groups</h2>

      <h3>Roster</h3>
      {error && <p className="error">{error}</p>}
      <form className="roster-form" onSubmit={addPlayer}>
        <input placeholder="Battletag (Name#1234)" value={newTag} onChange={(e) => setNewTag(e.target.value)} />
        <input placeholder="Display name (optional)" value={newName} onChange={(e) => setNewName(e.target.value)} />
        <button type="submit">Add</button>
      </form>
      <table className="table">
        <thead>
          <tr><th>Name</th><th>Battletag</th><th>Active</th><th></th></tr>
        </thead>
        <tbody>
          {players.map((p) => (
            <tr key={p.id} className={p.active ? '' : 'inactive'}>
              <td>{p.display_name}{p.is_primary ? ' (you)' : ''}</td>
              <td>{p.battletag}</td>
              <td><button onClick={() => toggleActive(p)}>{p.active ? 'Active' : 'Inactive'}</button></td>
              <td>{!p.is_primary && <button onClick={() => remove(p)}>Remove</button>}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Win rate by group</h3>
      <table className="table">
        <thead>
          <tr><th>Group</th><th>Games</th><th>Win rate</th></tr>
        </thead>
        <tbody>
          {groups.map((g) => (
            <tr key={g.players.join('|')}>
              <td>{g.players.join(' + ')}</td>
              <td>{g.games_played}</td>
              <td>{g.win_rate}%</td>
            </tr>
          ))}
          {!groups.length && (
            <tr><td colSpan={3} className="empty">No shared matches synced yet.</td></tr>
          )}
        </tbody>
      </table>
    </section>
  );
}
