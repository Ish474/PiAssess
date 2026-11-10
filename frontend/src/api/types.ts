// Shared API types mirroring the backend schemas.

export interface User {
  id: number;
  username: string;
  full_name: string;
  role: "admin" | "exam_controller" | "teacher" | "viewer";
  is_active: boolean;
  must_change_password: boolean;
  last_login_at: string | null;
}

export interface Section {
  id: number;
  name: string;
}

export interface Subject {
  id: number;
  name: string;
  code: string;
  max_marks: number;
}

export interface Klass {
  id: number;
  name: string;
  level: number | null;
  sections: Section[];
  subjects: Subject[];
  student_count: number;
}

export interface Student {
  id: number;
  student_code: string;
  admission_no: string;
  full_name: string;
  father_name: string;
  mother_name: string;
  class_id: number;
  section_id: number | null;
  roll_no: number | null;
  dob: string | null;
  gender: string;
  phone: string;
  email: string;
  address: string;
  admission_date: string | null;
  status: "active" | "inactive" | "passed" | "transferred";
  class_name: string;
  section_name: string;
  created_at: string;
}

export interface StudentList {
  items: Student[];
  total: number;
  page: number;
  page_size: number;
}

export interface ImportField {
  key: string;
  label: string;
}

export interface ImportPreviewRow {
  row_number: number;
  data: Record<string, string>;
  errors: string[];
}

export interface ImportPreview {
  columns: string[];
  rows: ImportPreviewRow[];
  valid_count: number;
  error_count: number;
  duplicate_count: number;
  mapping_hint: Record<string, string>;
}

export interface ImportResult {
  imported: number;
  skipped: number;
  first_student_code: string;
  codes: string[];
}

export interface Exam {
  id: number;
  name: string;
  exam_type: string;
  academic_session: string;
  class_id: number;
  subject_id: number | null;
  exam_date: string | null;
  max_marks: number;
  passing_marks: number;
  negative_marks: number;
  duration_minutes: number;
  status: "draft" | "ready" | "published" | "archived";
  instructions: string;
  class_name: string;
  subject_name: string;
  student_count: number;
  created_at: string;
}

export interface ExamList {
  items: Exam[];
  total: number;
}

export interface Doc {
  id: number;
  category: string;
  title: string;
  file_name: string;
  mime_type: string;
  file_size: number;
  uploaded_by: string;
  is_archived: boolean;
  created_at: string;
}

export interface DocumentList {
  items: Doc[];
  total: number;
}

export interface Activity {
  id: number;
  username: string;
  action: string;
  entity: string;
  entity_id: string;
  details: string;
  created_at: string;
}

export interface RecentExam {
  id: number;
  name: string;
  class_name: string;
  exam_date: string | null;
  student_count: number;
  status: string;
  results_available: boolean;
}

export interface Dashboard {
  total_students: number;
  total_examinations: number;
  total_subjects: number;
  average_performance: number | null;
  recent_exams: RecentExam[];
  activity: Activity[];
  checklist: Record<string, boolean>;
}

export interface Settings {
  school_name: string;
  school_address: string;
  school_tagline: string;
  academic_session: string;
  student_id_prefix: string;
  passing_marks_default: number;
  exam_types: string[];
  default_question_template: string;
  ai_provider: string;
  ai_base_url: string;
  ai_model: string;
  ai_api_key_set: boolean;
  ai_api_key_masked: string;
  logo_url: string;
}

/* ------------------------------------------------- questions ---- */
export const QUESTION_TYPE_LABELS: Record<string, string> = {
  mcq: "Multiple Choice",
  fill_blank: "Fill in the Blank",
  true_false: "True or False",
  match_following: "Match the Following",
  very_short: "Very Short Answer",
  short: "Short Answer",
  long: "Long Answer",
  numerical: "Numerical Problem",
  case_based: "Case-Based",
  assertion_reason: "Assertion & Reason",
  logical_reasoning: "Logical Reasoning",
  application: "Application-Based",
  hots: "HOTS",
};

export const DIFFICULTY_LABELS: Record<string, string> = {
  easy: "Easy",
  moderate: "Moderate",
  challenging: "Challenging",
  advanced: "Advanced",
  mixed: "Mixed",
};

export const VERIFICATION_LABELS: Record<string, string> = {
  verified: "Verified",
  needs_review: "Needs Review",
  unverified: "Unverified",
};

export interface Question {
  id: number;
  class_id: number;
  subject_id: number | null;
  exam_id: number | null;
  chapter: string;
  topic: string;
  qtype: string;
  difficulty: string;
  marks: number;
  text: string;
  options: string[];
  correct_answer: string;
  explanation: string;
  keywords: string[];
  marking_notes: string;
  check_expression: string;
  verification: "verified" | "needs_review" | "unverified";
  verification_note: string;
  source: string;
  created_at: string;
}

export interface QuestionList {
  items: Question[];
  total: number;
  page: number;
  page_size: number;
}

export interface DraftQuestion {
  qtype: string;
  difficulty: string;
  marks: number;
  text: string;
  options: string[];
  correct_answer: string;
  explanation: string;
  keywords: string[];
  marking_notes: string;
  check_expression: string;
  verification: string;
  verification_note: string;
}

export interface GenerateTypeRow {
  type: string;
  count: number;
  difficulty: string;
  marks: number;
}

export interface GenerateResponse {
  questions: DraftQuestion[];
  provider: string;
  model: string;
  skipped: number;
  skipped_notes: string[];
}

export interface BulkSaveResponse {
  saved: number;
  duplicates_skipped: number;
  ids: number[];
  paper_id: number | null;
}

export interface PaperItem {
  question_id: number;
  position: number;
  marks: number;
  question: Question;
}

export interface Paper {
  id: number;
  exam_id: number;
  class_id: number;
  title: string;
  instructions: string;
  total_marks: number;
  exam_name: string;
  class_name: string;
  subject_name: string;
  exam_date: string | null;
  duration_minutes: number;
  academic_session: string;
  exam_max_marks: number;
  items: PaperItem[];
}

export interface AIStatus {
  configured: boolean;
  provider: string;
  model: string;
  base_url: string;
}

/* ------------------------------- OMR scanning ------------------------------ */
export interface OmrScan {
  id: number;
  exam_id: number;
  set_letter: string;
  student_id: number | null;
  student_name: string | null;
  original_name: string;
  status: "pending" | "processing" | "processed" | "failed" | "review";
  confidence_band: "" | "GREEN" | "YELLOW" | "RED";
  score: number | null;
  max_score: number | null;
  error_message: string;
  processed_at: string | null;
  created_at: string;
}

export interface OmrScanList {
  items: OmrScan[];
  summary: {
    total: number;
    processed: number;
    needs_review: number;
    failed: number;
    pending: number;
  };
}

export interface OmrScanRow {
  position: number;
  marks: number;
  integer?: boolean;
  n_opts?: number;
  chosen: number | null;
  key: number | null;
  fill: number;
  verdict: "answered" | "unanswered" | "multi" | "review";
  correct: boolean;
  overridden?: boolean;
}

export interface OmrScanDetail extends OmrScan {
  responses: OmrScanRow[];
}

/* --------------------------------- results --------------------------------- */
export interface ResultRow {
  scan_id: number;
  student_id: number | null;
  student_name: string | null;
  roll_no: number | null;
  sheet: string;
  set: string;
  score: number;
  max_score: number;
  percent: number;
  passed: boolean;
  band: "" | "GREEN" | "YELLOW" | "RED";
  rank: number | null;
}

export interface ExamResults {
  exam: {
    id: number;
    name: string;
    class_name: string;
    subject_name: string;
    exam_date: string | null;
    max_marks: number;
    passing_marks: number;
    negative_marks: number;
    status: string;
  };
  rows: ResultRow[];
  stats: {
    sheets_scored: number;
    students_ranked: number;
    unassigned: number;
    highest: number | null;
    average_percent: number | null;
    pass_count: number;
    pass_percent: number | null;
  };
}

export interface NotificationItem {
  id: number;
  username: string;
  action: string;
  entity: string;
  details: string;
  created_at: string;
}

/* --------------------------------- backups ---------------------------------- */
export interface BackupFile {
  name: string;
  size: number;
  created_at: string;
}

export interface BackupStatus {
  auto_enabled: boolean;
  interval_hours: number;
  drive_connected: boolean;
  drive_folder_id: string;
  drive_last_upload: string | null;
}

export interface BackupOverview {
  backups: BackupFile[];
  status: BackupStatus;
}

export interface DriveFile {
  id: string;
  name: string;
  size?: number;
  createdTime?: string;
}
