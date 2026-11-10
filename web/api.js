import {app} from './state.js';

export async function api(path, {method='GET', body, workspace=app.workspace}={}) {
  const query = path.includes('?') ? '&' : '?';
  const scoped = workspace ? path + query + 'workspace=' + encodeURIComponent(workspace) : path;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 90000);
  try {
    const response = await fetch(scoped, {
      method, cache:'no-store', signal:controller.signal,
      headers: body === undefined ? {} : {'Content-Type':'application/json','X-NEXUS-Local':'1'},
      body:body === undefined ? undefined : JSON.stringify(body),
    });
    let result;
    try { result = await response.json(); } catch { throw new Error('The local server returned an unreadable response. Refresh to check your workspace.'); }
    if (!response.ok) throw new Error(result.error || 'The local request could not be completed.');
    return result;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('The request timed out. Its outcome is unconfirmed. Refresh before trying the action again.');
    if (error instanceof TypeError) throw new Error('Could not reach the local NEXUS server. Check that it is running, then retry.');
    throw error;
  } finally { clearTimeout(timer); }
}
export const post = (path, body, workspace=app.workspace) => api(path, {method:'POST', body, workspace});
