export const app = {
  workspace: new URLSearchParams(location.search).get('workspace') || '',
  view: 'overview', stale: false, busy: false, loaded: false, error: false, workspaces: [],
  assistantState: 'Ready', audioState: 'idle', modal: null, focusReturn: null,
  memoryResults: null, messageSignature: '',
  data: {tasks: [], events: [], projects: [], notes: [], memories: [], pending: [], audit: [], messages: []},
};
export const VIEW_NAMES = {overview:'Command Center', assistant:'Assistant', projects:'Projects', tasks:'Tasks', events:'Calendar', notes:'Meetings', memory:'Memory', approvals:'Approvals', activity:'Activity', settings:'Settings'};
