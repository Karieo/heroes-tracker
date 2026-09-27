const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001';

async function request(path, options) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  version: () => request('/api/version'),

  listPlayers: (includeInactive) => request(`/api/players${includeInactive ? '?all=1' : ''}`),
  addPlayer: (battletag, displayName) =>
    request('/api/players', { method: 'POST', body: JSON.stringify({ battletag, display_name: displayName }) }),
  updatePlayer: (id, patch) => request(`/api/players/${id}`, { method: 'PUT', body: JSON.stringify(patch) }),
  deletePlayer: (id) => request(`/api/players/${id}`, { method: 'DELETE' }),

  matches: (params = {}) => request(`/api/matches?${new URLSearchParams(params)}`),
  matchDetail: (matchId) => request(`/api/matches/${matchId}`),

  heroes: () => request('/api/heroes'),
  heroStats: (hero, params = {}) => request(`/api/heroes/${encodeURIComponent(hero)}/stats?${new URLSearchParams(params)}`),
  heroTalents: (hero, params = {}) => request(`/api/heroes/${encodeURIComponent(hero)}/talents?${new URLSearchParams(params)}`),
  heroMatchups: (hero, params = {}) => request(`/api/heroes/${encodeURIComponent(hero)}/matchups?${new URLSearchParams(params)}`),

  groups: (minGames) => request(`/api/groups?min_games=${minGames || 1}`),
};
