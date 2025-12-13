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
    case 'goal': return '#4fc3f7';
    case 'objective': return '#26a69a';
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
    case 'PREREQ': return 'solid';
    case 'targets': return 'solid';
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
        'label': '',
        'color': '#e6edf3',
        'text-outline-color': '#0a0c10',
        'text-outline-width': 2,
        'width': 'mapData(type, 0, 0, 28, 28)',
        'height': 'mapData(type, 0, 0, 28, 28)'
      }},
      { selector: 'edge', style: {
        'line-color': '#78839a',
        'width': 2,
        'curve-style': 'bezier',
        'target-arrow-shape': 'triangle',
        'target-arrow-color': '#78839a',
        'line-style': ele => relStyle(ele.data('rel')),
        'opacity': 0.35
      }}
    ],
    layout: { name: 'cose', padding: 48, nodeRepulsion: 90000 }
  });
  $('graph')._cy = cy;

  cy.on('tap', 'node', (evt) => {
    const d = evt.target.data();
    axios.get('/api/node_details', { params: { uid: d.id } }).then(({ data }) => {
      $('analysisOut').textContent = JSON.stringify(data.details, null, 2);
    });
    $('graph')._selected = d.id;
  });

  cy.on('mouseover', 'node', (evt) => {
    const n = evt.target;
    n.style('label', n.data('label'));
  });
  cy.on('mouseout', 'node', () => {
    updateLabels();
  });

  function updateLabels() {
    const show = cy.zoom() >= 1.1;
    cy.nodes().forEach(n => n.style('label', show ? n.data('label') : ''));
  }
  updateLabels();
  cy.on('zoom', updateLabels);

  function applyFilters() {
    const allowed = new Set();
    if ($('cbSubject').checked) allowed.add('subject');
    if ($('cbSection').checked) allowed.add('section');
    if ($('cbTopic').checked) allowed.add('topic');
    if ($('cbSkill').checked) allowed.add('skill');
    if ($('cbMethod').checked) allowed.add('method');
    if ($('cbGoal').checked) allowed.add('goal');
    if ($('cbObjective').checked) allowed.add('objective');
    const relAllowed = new Set();
    if ($('relContains').checked) relAllowed.add('contains');
    if ($('relHasSkill').checked) relAllowed.add('has_skill');
    if ($('relPrereq').checked) relAllowed.add('PREREQ');
    if ($('relTargets').checked) relAllowed.add('targets');
    if ($('relLinked').checked) relAllowed.add('linked');
    cy.nodes().forEach(n => {
      const show = allowed.has(n.data('type'));
      n.style('display', show ? 'element' : 'none');
    });
    cy.edges().forEach(e => {
      const s = cy.getElementById(e.data('source'));
      const t = cy.getElementById(e.data('target'));
      const show = s.style('display') !== 'none' && t.style('display') !== 'none' && relAllowed.has(e.data('rel'));
      e.style('display', show ? 'element' : 'none');
    });
  }

  ['cbSubject','cbSection','cbTopic','cbSkill','cbMethod','cbGoal','cbObjective'].forEach(id => {
    $(id).addEventListener('change', applyFilters);
  });
  ['relContains','relHasSkill','relPrereq','relTargets','relLinked'].forEach(id => {
    $(id).addEventListener('change', applyFilters);
  });

  $('degreeSlider').addEventListener('input', () => {
    const deg = parseInt($('degreeSlider').value, 10);
    $('degreeValue').textContent = String(deg);
    cy.nodes().forEach(n => {
      const k = n.connectedEdges().length;
      n.style('display', k >= deg ? 'element' : 'none');
    });
    cy.edges().forEach(e => {
      const s = cy.getElementById(e.data('source'));
      const t = cy.getElementById(e.data('target'));
      const show = s.style('display') !== 'none' && t.style('display') !== 'none';
      e.style('display', show ? 'element' : 'none');
    });
  });

  $('searchBtn').addEventListener('click', () => {
    const q = $('searchBox').value.trim();
    axios.get('/api/search', { params: { q, limit: 50 } }).then(({ data }) => {
      const ids = new Set((data.items || []).map(it => it.uid));
      cy.nodes().forEach(n => {
        const match = ids.has(n.id());
        n.style('border-width', match ? 3 : 0);
        n.style('border-color', match ? '#f5a623' : '#000');
        if (match) n.style('label', n.data('label'));
      });
    });
  });
}

async function bindActions() {
  $('refreshGraph').addEventListener('click', renderGraph);
  $('fitGraphBtn').addEventListener('click', () => {
    const container = $('graph');
    if (container && container._cy) {
      container._cy.fit();
    }
  });
  $('zoomInBtn').addEventListener('click', () => {
    const cy = $('graph')._cy;
    if (cy) cy.zoom(cy.zoom() * 1.2);
  });
  $('zoomOutBtn').addEventListener('click', () => {
    const cy = $('graph')._cy;
    if (cy) cy.zoom(cy.zoom() / 1.2);
  });

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

  $('addTopicGoalBtn').addEventListener('click', async () => {
    const payload = { title: $('goalTitle').value, topic_uid: $('goalTopic').value };
    await axios.post('/api/topic_goals', payload);
    await renderGraph();
  });

  $('addTopicObjectiveBtn').addEventListener('click', async () => {
    const payload = { title: $('objTitle').value, topic_uid: $('objTopic').value };
    await axios.post('/api/topic_objectives', payload);
    await renderGraph();
  });

  $('syncNeo4jBtn').addEventListener('click', async () => {
    const { data } = await axios.post('/api/neo4j_sync');
    $('analysisOut').textContent = JSON.stringify(data, null, 2);
    await renderGraph();
  });

  $('normalizeKbBtn').addEventListener('click', async () => {
    const { data } = await axios.post('/api/normalize_kb');
    $('analysisOut').textContent = JSON.stringify(data, null, 2);
    await renderGraph();
  });

  $('analyzeBtn').addEventListener('click', async () => {
    const { data } = await axios.get('/api/analysis');
    $('analysisOut').textContent = JSON.stringify(data, null, 2);
  });
  $('rerunLayoutBtn').addEventListener('click', () => {
    const cy = $('graph')._cy;
    const name = $('layoutSelect').value;
    if (cy) cy.layout({ name }).run();
  });
  $('exportJsonBtn').addEventListener('click', async () => {
    const subjectUid = $('subjectFilter').value || '';
    const { data } = await axios.get('/api/graph', { params: { subject_uid: subjectUid } });
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'graph.json';
    a.click();
  });
  $('loadNeighborhoodBtn').addEventListener('click', async () => {
    const cy = $('graph')._cy;
    const center = $('graph')._selected;
    if (!center || !cy) return;
    const { data } = await axios.get('/v1/graph/viewport', { params: { center_uid: center, depth: 1 } });
    const existingIds = new Set(cy.nodes().map(n => n.id()));
    const existingEdges = new Set(cy.edges().map(e => e.id()));
    const newElements = [];
    (data.nodes || []).forEach(n => {
      const id = n.uid || String(n.id);
      if (!existingIds.has(id)) {
        newElements.push({ data: { id, label: n.label || '', type: (n.labels || [])[0] || 'topic' } });
      }
    });
    (data.edges || []).forEach(e => {
      const id = `${e.from}->${e.to}`;
      if (!existingEdges.has(id)) {
        newElements.push({ data: { id, source: String(e.from), target: String(e.to), rel: e.type || 'linked' } });
      }
    });
    cy.add(newElements);
    cy.layout({ name: 'cose' }).run();
  });
  // Populate selects via list endpoints
  const subjSel = $('sectionSubject');
  const skSubjSel = $('skillSubject');
  axios.get('/api/list', { params: { kind: 'subjects' } }).then(({ data }) => {
    const items = data.items || [];
    subjSel.innerHTML = items.map(it => `<option value="${it.uid}">${it.title}</option>`).join('');
    skSubjSel.innerHTML = subjSel.innerHTML;
    // fill sections of selected subject
    const su = subjSel.value;
    axios.get('/api/list', { params: { kind: 'sections', subject_uid: su } }).then(({ data }) => {
      $('topicSection').innerHTML = (data.items || []).map(it => `<option value="${it.uid}">${it.title}</option>`).join('');
    });
    // skills and methods for linking
    axios.get('/api/list', { params: { kind: 'skills', subject_uid: su } }).then(({ data }) => {
      $('linkSkill').innerHTML = (data.items || []).map(it => `<option value="${it.uid}">${it.title}</option>`).join('');
    });
    axios.get('/api/list', { params: { kind: 'methods' } }).then(({ data }) => {
      $('linkMethod').innerHTML = (data.items || []).map(it => `<option value="${it.uid}">${it.title}</option>`).join('');
    });
    // topics for goals/objectives
    axios.get('/api/list', { params: { kind: 'topics' } }).then(({ data }) => {
      const opts = (data.items || []).map(it => `<option value="${it.uid}">${it.title}</option>`).join('');
      $('goalTopic').innerHTML = opts;
      $('objTopic').innerHTML = opts;
    });
  });
}

window.addEventListener('DOMContentLoaded', async () => {
  await bindActions();
  await renderGraph();
});
