-- KnowledgeBaseAI PostgreSQL schema
-- Entities: subject, section, topic, skill, method, example, error
-- Relations: strict hierarchy subject→section→topic, skills DAG per subject

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Subjects
CREATE TABLE IF NOT EXISTS subjects (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  uid TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  description TEXT
);

-- Sections within a subject
CREATE TABLE IF NOT EXISTS sections (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  uid TEXT NOT NULL UNIQUE,
  subject_id UUID REFERENCES subjects(id) ON DELETE CASCADE,
  subject_uid TEXT REFERENCES subjects(uid) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  order_index INTEGER NOT NULL DEFAULT 0
);

-- Topics within a section
CREATE TABLE IF NOT EXISTS topics (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  uid TEXT NOT NULL UNIQUE,
  section_id UUID REFERENCES sections(id) ON DELETE CASCADE,
  section_uid TEXT REFERENCES sections(uid) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  -- mastery thresholds per base_concept.md
  accuracy_threshold NUMERIC(4,2) NOT NULL DEFAULT 0.85, -- 0..1
  critical_errors_max INTEGER NOT NULL DEFAULT 0,
  median_time_threshold_seconds INTEGER NOT NULL DEFAULT 600
);

-- Skills within a subject (DAG via prerequisites)
CREATE TABLE IF NOT EXISTS skills (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  uid TEXT NOT NULL UNIQUE,
  subject_id UUID REFERENCES subjects(id) ON DELETE CASCADE,
  subject_uid TEXT REFERENCES subjects(uid) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  definition TEXT,
  applicability_types TEXT[],
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived'))
);

-- Methods (can be reused across skills)
CREATE TABLE IF NOT EXISTS methods (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  uid TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  method_text TEXT NOT NULL,
  applicability_types TEXT[] -- optional typing per base_concept.md
);

-- Examples
CREATE TABLE IF NOT EXISTS examples (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  uid TEXT NOT NULL UNIQUE,
  subject_id UUID REFERENCES subjects(id) ON DELETE CASCADE,
  subject_uid TEXT REFERENCES subjects(uid) ON DELETE CASCADE,
  topic_id UUID REFERENCES topics(id) ON DELETE SET NULL,
  topic_uid TEXT REFERENCES topics(uid) ON DELETE SET NULL,
  title TEXT NOT NULL,
  statement TEXT NOT NULL,
  difficulty_level TEXT NOT NULL DEFAULT 'medium'
);

-- Errors taxonomy
CREATE TABLE IF NOT EXISTS errors (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  uid TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  description TEXT,
  error_type TEXT
);

-- Relations

-- Topic ↔ Skill (target skills for topic)
CREATE TABLE IF NOT EXISTS topic_skills (
  topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
  skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  PRIMARY KEY (topic_id, skill_id)
);

-- Removed id-based skill_methods in favor of uid-based version below

CREATE TABLE IF NOT EXISTS skill_dependencies (
    parent_skill_uid VARCHAR(50) REFERENCES skills(uid) ON DELETE CASCADE,
    child_skill_uid VARCHAR(50) REFERENCES skills(uid) ON DELETE CASCADE,
    dependency_type VARCHAR(20) NOT NULL DEFAULT 'prerequisite', -- prerequisite, reinforces, extends
    strength DECIMAL(3,2) DEFAULT 1.0, -- Сила связи от 0.0 до 1.0
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (parent_skill_uid, child_skill_uid),
    CHECK (parent_skill_uid != child_skill_uid),
    CHECK (strength >= 0.0 AND strength <= 1.0)
);

-- Таблица связей навыков и методов
CREATE TABLE IF NOT EXISTS skill_methods (
    skill_uid VARCHAR(50) REFERENCES skills(uid) ON DELETE CASCADE,
    method_uid VARCHAR(50) REFERENCES methods(uid) ON DELETE CASCADE,
    weight VARCHAR(20) NOT NULL DEFAULT 'secondary', -- primary, secondary, auxiliary
    confidence DECIMAL(4,3) DEFAULT 0.5, -- Уверенность в связи от 0.0 до 1.0
    is_auto_generated BOOLEAN DEFAULT false, -- Автоматически сгенерированная связь
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (skill_uid, method_uid),
    CHECK (confidence >= 0.0 AND confidence <= 1.0),
    CHECK (weight IN ('primary', 'secondary', 'auxiliary'))
);

-- Example ↔ Skill with role {target, auxiliary, context}
CREATE TABLE IF NOT EXISTS example_skills (
  example_id UUID NOT NULL REFERENCES examples(id) ON DELETE CASCADE,
  skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('target','auxiliary','context')),
  UNIQUE (example_id, skill_id)
);

-- Error ↔ Skill
CREATE TABLE IF NOT EXISTS error_skills (
  error_id UUID NOT NULL REFERENCES errors(id) ON DELETE CASCADE,
  skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  PRIMARY KEY (error_id, skill_id)
);

-- Error ↔ Example
CREATE TABLE IF NOT EXISTS error_examples (
  error_id UUID NOT NULL REFERENCES errors(id) ON DELETE CASCADE,
  example_id UUID NOT NULL REFERENCES examples(id) ON DELETE CASCADE,
  PRIMARY KEY (error_id, example_id)
);

-- Skill prerequisites (DAG per subject)
CREATE TABLE IF NOT EXISTS skill_prerequisites (
  subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
  skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  depends_on_skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  CHECK (skill_id <> depends_on_skill_id),
  PRIMARY KEY (subject_id, skill_id, depends_on_skill_id)
);

-- Ensure skills in prerequisite belong to the same subject
CREATE OR REPLACE FUNCTION check_prereq_same_subject() RETURNS TRIGGER AS $$
DECLARE
  s1 UUID;
  s2 UUID;
BEGIN
  SELECT subject_id INTO s1 FROM skills WHERE id = NEW.skill_id;
  SELECT subject_id INTO s2 FROM skills WHERE id = NEW.depends_on_skill_id;
  IF s1 IS NULL OR s2 IS NULL THEN
    RAISE EXCEPTION 'Skill IDs must exist';
  END IF;
  IF s1 <> NEW.subject_id OR s2 <> NEW.subject_id THEN
    RAISE EXCEPTION 'Both skills must belong to subject %', NEW.subject_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prereq_same_subject ON skill_prerequisites;
CREATE TRIGGER trg_prereq_same_subject
BEFORE INSERT OR UPDATE ON skill_prerequisites
FOR EACH ROW EXECUTE FUNCTION check_prereq_same_subject();

-- DAG acyclicity check: prevent cycles in skill prerequisites within subject
CREATE OR REPLACE FUNCTION check_skill_prerequisite_acyclic() RETURNS TRIGGER AS $$
DECLARE
  cycle_found BOOLEAN;
BEGIN
  -- Detect path from NEW.depends_on_skill_id to NEW.skill_id
  WITH RECURSIVE reach(n) AS (
    SELECT NEW.depends_on_skill_id
    UNION
    SELECT sp.depends_on_skill_id
    FROM skill_prerequisites sp
    JOIN reach r ON sp.skill_id = r.n
    WHERE sp.subject_id = NEW.subject_id
  )
  SELECT EXISTS (
    SELECT 1 FROM reach WHERE n = NEW.skill_id
  ) INTO cycle_found;

  IF cycle_found THEN
    RAISE EXCEPTION 'Cycle detected in prerequisites for subject %: % -> %', NEW.subject_id, NEW.skill_id, NEW.depends_on_skill_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_skill_prereq_acyclic ON skill_prerequisites;
CREATE TRIGGER trg_skill_prereq_acyclic
BEFORE INSERT OR UPDATE ON skill_prerequisites
FOR EACH ROW EXECUTE FUNCTION check_skill_prerequisite_acyclic();

-- Attempts (diagnostics) — optional, for mastery evaluation
CREATE TABLE IF NOT EXISTS attempts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  learner_id TEXT NOT NULL,
  example_id UUID NOT NULL REFERENCES examples(id) ON DELETE CASCADE,
  started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  finished_at TIMESTAMP WITH TIME ZONE,
  time_spent_seconds INTEGER CHECK (time_spent_seconds >= 0),
  accuracy NUMERIC(4,2) CHECK (accuracy BETWEEN 0 AND 1),
  critical_errors_count INTEGER DEFAULT 0 CHECK (critical_errors_count >= 0)
);

-- Attempt ↔ Skill evaluation
CREATE TABLE IF NOT EXISTS attempt_skill_evaluations (
  attempt_id UUID NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
  skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  role TEXT CHECK (role IN ('target','auxiliary','context')),
  score NUMERIC(4,2) CHECK (score BETWEEN 0 AND 1),
  PRIMARY KEY (attempt_id, skill_id)
);

-- Attempt error events
CREATE TABLE IF NOT EXISTS attempt_error_events (
  attempt_id UUID NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
  error_id UUID NOT NULL REFERENCES errors(id) ON DELETE CASCADE,
  skill_id UUID REFERENCES skills(id) ON DELETE SET NULL,
  example_id UUID REFERENCES examples(id) ON DELETE SET NULL,
  severity TEXT NOT NULL CHECK (severity IN ('critical','minor')),
  occurred_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_sections_subject ON sections(subject_id);
CREATE INDEX IF NOT EXISTS idx_sections_subject_uid ON sections(subject_uid);
CREATE INDEX IF NOT EXISTS idx_topics_section ON topics(section_id);
CREATE INDEX IF NOT EXISTS idx_topics_section_uid ON topics(section_uid);
CREATE INDEX IF NOT EXISTS idx_skills_subject ON skills(subject_id);
CREATE INDEX IF NOT EXISTS idx_skills_subject_uid ON skills(subject_uid);
CREATE INDEX IF NOT EXISTS idx_examples_subject ON examples(subject_id);
CREATE INDEX IF NOT EXISTS idx_examples_subject_uid ON examples(subject_uid);
CREATE INDEX IF NOT EXISTS idx_examples_topic_uid ON examples(topic_uid);
CREATE INDEX IF NOT EXISTS idx_example_skills_role ON example_skills(role);

-- Safe alterations to ensure columns exist when upgrading from older schema
ALTER TABLE sections ADD COLUMN IF NOT EXISTS subject_uid TEXT REFERENCES subjects(uid) ON DELETE CASCADE;
ALTER TABLE sections ADD COLUMN IF NOT EXISTS order_index INTEGER NOT NULL DEFAULT 0;
ALTER TABLE topics ADD COLUMN IF NOT EXISTS section_uid TEXT REFERENCES sections(uid) ON DELETE CASCADE;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS subject_uid TEXT REFERENCES subjects(uid) ON DELETE CASCADE;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS applicability_types TEXT[];
ALTER TABLE skills ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE examples ADD COLUMN IF NOT EXISTS subject_uid TEXT REFERENCES subjects(uid) ON DELETE CASCADE;
ALTER TABLE examples ADD COLUMN IF NOT EXISTS topic_uid TEXT REFERENCES topics(uid) ON DELETE SET NULL;
ALTER TABLE examples ADD COLUMN IF NOT EXISTS difficulty_level TEXT NOT NULL DEFAULT 'medium';
ALTER TABLE errors ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE errors ADD COLUMN IF NOT EXISTS error_type TEXT;

-- End of schema