function $(id) { return document.getElementById(id); }

async function fetchGraph(subjectUid) {
  const params = subjectUid ? { params: { subject_uid: subjectUid } } : {};
  const { data } = await axios.get('/api/graph', params);
  return data;
}

function typeColor(type) {
  switch (type) {
    case 'subject': return '#6da7ff';
    case 'section': return '#7bd389';
    case 'topic': return '#f7c948';
    case 'skill': return '#ff8c69';
    case 'method': return '#c792ea';
    default: return '#9aa4b2';
  }
}

function relStyle(rel) {
  switch (rel) {
    case 'contains': return 'solid';
    case 'has_skill': return 'solid';
    case 'primary': return 'solid';
    case 'secondary': return 'dashed';
    case 'auxiliary': return 'dotted';
    default: return 'solid';
  }
}

async function renderGraph() {
  const subjectUid = $('subjectFilter').value || '';
  const graph = await fetchGraph(subjectUid);
  const cy = cytoscape({
    container: $('graph'),
    elements: [...graph.nodes, ...graph.edges],
    style: [
      { selector: 'node', style: {
        'background-color': ele => typeColor(ele.data('type')),
        'label': 'data(label)',
        'color': '#e6edf3',
        'text-outline-color': '#0a0c10',
        'text-outline-width': 2,
        'width': 'mapData(type, 0, 0, 24, 24)',
        'height': 'mapData(type, 0, 0, 24, 24)'
      }},
      { selector: 'edge', style: {
        'line-color': '#78839a',
        'width': 2,
        'curve-style': 'bezier',
        'target-arrow-shape': 'triangle',
        'target-arrow-color': '#78839a',
        'line-style': ele => relStyle(ele.data('rel')),
      }}
    ],
    layout: { name: 'cose', padding: 30, nodeRepulsion: 50000 }
  });

  cy.on('tap', 'node', (evt) => {
    const d = evt.target.data();
    console.info('Node clicked:', d);
  });
}

async function bindActions() {
  $('refreshGraph').addEventListener('click', renderGraph);

  $('addSubjectBtn').addEventListener('click', async () => {
    const payload = { title: $('subjTitle').value, description: $('subjDesc').value };
    await axios.post('/api/subjects', payload);
    await renderGraph();
  });

  $('addSectionBtn').addEventListener('click', async () => {
    const payload = { title: $('sectionTitle').value, description: $('sectionDesc').value, subject_uid: $('sectionSubject').value };
    await axios.post('/api/sections', payload);
    await renderGraph();
  });

  $('addTopicBtn').addEventListener('click', async () => {
    const payload = { title: $('topicTitle').value, description: $('topicDesc').value, section_uid: $('topicSection').value };
    await axios.post('/api/topics', payload);
    await renderGraph();
  });

  $('addSkillBtn').addEventListener('click', async () => {
    const payload = { title: $('skillTitle').value, definition: $('skillDef').value, subject_uid: $('skillSubject').value };
    await axios.post('/api/skills', payload);
    await renderGraph();
  });

  $('addMethodBtn').addEventListener('click', async () => {
    const types = $('methodTypes').value.split(',').map(s => s.trim()).filter(Boolean);
    const payload = { title: $('methodTitle').value, method_text: $('methodText').value, applicability_types: types };
    await axios.post('/api/methods', payload);
    await renderGraph();
  });

  $('linkBtn').addEventListener('click', async () => {
    const payload = {
      skill_uid: $('linkSkill').value,
      method_uid: $('linkMethod').value,
      weight: $('linkWeight').value,
      confidence: parseFloat($('linkConf').value) || 0.9
    };
    await axios.post('/api/skill_methods', payload);
    await renderGraph();
  });
}

window.addEventListener('DOMContentLoaded', async () => {
  await bindActions();
  await renderGraph();
});