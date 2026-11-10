# PiAssess User Manual
**Pi World School, Forbesganj, Bihar — Academic Evaluation Suite**

This manual explains PiAssess in plain language for school staff.

---

## 1. Starting and signing in

1. Double-click **start_piassess.bat** on the computer where PiAssess is installed.
2. Your web browser opens at **http://localhost:8600**.
3. Type your **username** and **password**, then click **Sign in**.
4. The first-ever sign in uses username `admin` and password `admin123`.
   → Go to **Settings → Users**, click *Reset Password* and set a private password.

Keep the black window open while working — it is PiAssess running. Closing it stops the
program (your data is saved continuously, nothing is lost).

---

## 2. The Dashboard

The dashboard greets you and shows:

- **Four action cards** (question papers, OMR sheets, scanning, results) — these modules
  switch on in later phases; each card shows its phase number.
- **Quick statistics** — total students, examinations, subjects.
- **Recent Examinations** — latest exams with class, date and status.
- **Getting Started** — a step-by-step checklist for first-time setup. Click an item to go
  to that module.
- **Recent Activity** — who did what, and when.

---

## 3. Class & Subjects (do this first)

**Sidebar → Class & Subjects**

1. Click **Add Class** (e.g. "Class 5"). Classes 1–12 with sections A/B/C and standard
   subjects are created automatically the first time PiAssess starts.
2. Select a class on the left to:
   - **Add Section** (type a letter, e.g. D).
   - **Add Subject** with its **Maximum Marks** (e.g. Mathematics, 100).
3. Use the pencil to edit, the bin to delete. Deleting is blocked while students are still
   in the class — move them first.

---

## 4. Student Database

**Sidebar → Student Database**

### Add a single student
Click **Add Student**. The **Student ID** (e.g. `APWS-2026-0001`) is generated
automatically and never repeats. Fill name, class, section, roll number and the optional
details, then save.

### Import a whole class from Excel
1. Click **Import** and choose an Excel (.xlsx) or CSV file.
   The **first row must be headings**, e.g.:
   `Student Name | Class | Section | Roll Number | Father's Name | Date of Birth | Gender`
2. **Match columns** — PiAssess guesses the matches; correct them if needed.
3. **Check the rows** — every row is validated: missing names, unknown classes, duplicate
   admission numbers, bad dates. Problems are listed in red.
4. Click **Import Now**. Valid rows are saved; problem rows are **skipped and reported**,
   never half-saved. Fix them in your file and import again — only the new students are
   added.

### Finding and editing
- **Search** by name, Student ID or admission number; filter by class, section, status.
- Click a name to open the **profile**; use the pencil to edit, the bin to delete
  (deletion asks for confirmation and cannot be undone).
- **Export CSV / Excel** downloads the current list (respects the active filters).

---

## 5. Examination Manager

**Sidebar → Examination Manager**

Click **Create Examination** and fill in:
name, type (Weekly Test … Annual Examination), class, subject, date, maximum marks,
passing marks and duration. Status flow: *Draft → Ready → Published → Archived*.
In later phases, question papers, OMR sheets and results attach to this examination.

---

## 6. Document Library

**Sidebar → Document Library** — a central cupboard for school files.
Upload into categories (Question Papers, Answer Keys, OMR Sheets, Scanned Answer Sheets,
Results, Report Cards, Examination Reports). Only signed-in staff can download anything.
Archive old documents instead of deleting them.

---

## 7. Settings

**Sidebar → Settings** (administrator-only actions are marked)

- **School** — school name, address, and the official **logo upload** (PNG/JPG).
- **Academic** — academic session (2026-27), student-ID prefix (APWS), default passing
  marks, examination types.
- **AI Provider** — provider name, **service address (Base URL)**, model and API key for
  question generation. The key is stored safely and never shown again.
- **Users** — add staff accounts with roles:
  *Administrator* (everything) · *Exam Controller* (exams, OMR, results) ·
  *Teacher* (papers, evaluation, performance) · *Viewer* (read-only).
- **Backup & Data** — full backups (see section 7g below).

---

## 7a. AI Question Paper Generator

**Sidebar → AI Question Paper Generator** (Administrator, Exam Controller, Teacher)

First time: open **Settings → AI Provider** and fill in the Service Address, Model and API
key of any OpenAI-compatible provider (OpenRouter, OpenAI, Zhipu, Ollama on your own
computer, …). Until then the generator shows a reminder and keeps generation switched off.

The 5-step flow:

1. **Examination** — pick the exam the paper belongs to.
2. **Chapters & Material** — type chapter names and/or upload a PDF/DOCX/TXT extract.
   The uploaded text is the source of truth; the AI is told to stay inside it.
3. **Question Mix** — choose how many of each of the 13 question types (MCQ, fill in the
   blank, match the following, numerical, case-based, HOTS, …) with difficulty and marks.
4. **Generate & Review** — the AI drafts the questions and **every numerical answer is
   re-computed with SymPy**. Each draft carries an honest status:
   - **Verified** — the maths was proven correct by computation.
   - **Needs Review** — the check failed or something looks off; rework or regenerate.
   - **Unverified** — no automatic check was possible; a teacher must read it.
   You can edit any draft (editing resets its status), regenerate similar, or remove it.
5. **Saved** — questions go to the Question Bank and attach to the exam's paper.
   Exact duplicates are skipped automatically — the bank never keeps a question twice.

## 7b. Question Bank

**Sidebar → Question Bank** — every question the school owns, searchable and filterable
by class, type, difficulty and verification status. Teachers can add questions manually,
edit, verify or delete. The same question can never be saved twice.

## 7c. The Question Paper editor & printing

Open any examination from the **Examination Manager** (paper icon) or from the
generator's last step. The editor shows the ordered question list with arrows to
re-order and per-question marks; the right side is a **live print preview** with the
school logo and heading. Switch to the **Answer Key** tab for examiner-only answers,
then press **Print** — only the paper prints, on plain A4. Changes must be saved with
**Save Changes** before printing.

**PDF & Word export** — the **PDF** and **Word** buttons download a professionally
typeset file: school masthead with your official logo, paper title, class/subject/date
line, instructions box, numbered questions with marks in the margin, and **MCQ options
on one horizontal line** for each question, plus a total-marks footer and a
"Verified by" signature line. The PDF is typeset with a real LaTeX engine (tectonic —
it ships inside the project folder, nothing to install or configure), giving
print-shop quality alignment and properly rendered math notation ($2^3$, fractions,
roots) exactly as the AI wrote it. The question body flows in **two columns per
page** to fit more on each sheet, and every question is an unbreakable block —
if a question (or its MCQ options) does not fit in the space left on the page,
the whole question moves to the next page instead of being cut in half. Word files
carry the same logo and layout and are
fully editable for last-minute touches. Switch to the **Answer Key** tab first to
export the answer key with the marking scheme instead. If the LaTeX engine is ever
unavailable, the PDF is quietly built with the built-in engine instead — exports
never fail.

**OMR bubble sheets** — open **OMR Sheet Designer** in the sidebar (or use the
**OMR** button on any paper editor) to download a scanner-ready bubble sheet in
the classic entrance-exam style: **CLASS / SET corner tags**, a dark maroon
banner with your school logo, the test name with class / session / date, Time
and Test-code on the left with Maximum Marks on the right, a candidate block
(Name, Roll No., Section, Date, both signatures), a bordered *Instructions for
marking the OMR sheet* box, and **four parallel section boxes** of 20 questions
each — lettered bubbles (A B C D) for MCQs and digit bubbles (0–9) for
integer-type questions — each box with its own **Marks** line. Black
registration squares and a QR code identifying the examination sit around the
grid, with a *For office use* strip at the bottom. Bubble rows follow the
question paper's own numbering, so question 7 on the paper is question 7 on the
OMR sheet. Pick the paper set (**SET A / B / C / D**) in the designer — it is
printed on the corner tag so the sheet always matches the right question paper.
Papers with more than 80 objective questions automatically continue onto extra
pages. Print on plain A4; students darken the bubbles. To print **one file with
both**, use the **PDF + OMR** button on the paper editor (or the same option in
the **Examination Manager**'s OMR menu): the **OMR sheet comes first**, then the
question paper pages, and **every page is the same A4 size** — print the whole
file in one go and hand out the bubble sheet on top. For quick manual checking,
the OMR Sheet Designer can also print an **answer-key copy**: the
same sheet with every correct bubble darkened and a KEY COPY watermark across
it — questions whose answer is not set yet are starred instead.

---

## 7d. OMR Processing — scanning & auto-scoring

When the answer sheets come back, open **OMR Processing** in the sidebar.

1. **Choose the examination** and the **set** (A/B/C/D) the students wrote.
2. **Scan or photograph** each OMR sheet — a JPG or PNG image per student, or
   **one PDF containing the whole class**: when you upload a PDF, every page
   becomes its own sheet automatically (a whole stack scanned on the school
   photocopier lands as a single PDF — perfect). A phone photo is fine if the
   whole sheet is visible, flat and well lit.
3. **Upload & read** — each sheet is straightened automatically using the four
   black registration squares, then every bubble is read at its exact printed
   position and scored against the answer key. No AI is involved in reading
   bubbles; it is pure image detection, so the same sheet always reads the same.

Every sheet gets a traffic-light status:

- **Clean read (green)** — bubbles were read confidently; the score is final.
- **Needs review (amber)** — a faint mark or two darkened bubbles on one row
  was found; the row is not scored until a human confirms it.
- **Unreadable (red)** — the sheet could not be aligned (wrong set's sheet,
  cut-off corner, too dark a photo). The message explains what to fix; re-upload.

Use **View** on a reviewed sheet to see every question: what the machine read,
the answer key, and how dark each mark was. Click any letter to **correct a
reading by hand** (or clear it) — the score updates at once and the correction
is recorded in the activity log. Unread sheets can also be re-processed or
deleted; nothing is ever silently dropped.

**Negative marking** — by default a wrong answer simply scores 0. Exams that
use entrance-exam style marking can set **Negative Marking (per wrong answer)**
in the Examination Manager's exam form — for example `0.25` cuts ¼ mark for
every wrongly-darkened bubble, while blank questions always lose nothing. The
deduction is applied automatically in OMR scores (and shown on the OMR
Processing page while it is active).

**Assigning sheets to students** — the printed sheet has a handwritten roll
number, which no scanner can read honestly, so after evaluation open each
sheet in OMR Processing and pick its student from the dropdown (one click per
sheet, using the class list). Assigned sheets appear in results with the
student's name and rank.

---

## 7e. Results & Reports

Open **Results & Reports** in the sidebar and choose an examination. As soon
as at least one OMR sheet has been scored, the page shows:

- **Result table** — rank (with trophies for the top three), student name and
  roll number, set, score, percentage, PASS/FAIL against the exam's passing
  marks, and how cleanly the sheet was read. Sheets not yet assigned to a
  student still appear with their score — nothing is hidden.
- **Class statistics** — sheets scored, students ranked, highest score, class
  average and pass percentage.
- **Download result sheet (CSV)** — one click exports the whole table with the
  statistics footer, ready for Excel or printing.

---

## 7f. Notifications

The **bell icon** (top-right) lists the latest school activity — sheets
scanned, corrections made, students imported, papers exported — with an unread
counter that clears via **Mark all seen**. It is the same audit trail shown on
the Dashboard, always on hand wherever you are in the app.

---

## 7g. Backup & Data — automatic backups and Google Drive

Open **Settings → Backup & Data** (administrator only). A backup is a zip file
containing the complete database — students, examinations, results, settings —
plus every uploaded file (school logo, documents, scanned OMR sheets).

**Back up now** creates a backup immediately. It is stored in the
`backend/data/backups` folder and, when Google Drive is connected, uploaded to
the school's Drive folder automatically. Each backup also appears in the
**Backups on this computer** table, from where it can be downloaded (keep a
copy on a pen drive for extra safety) or deleted.

**Automatic backup** — switch it on and choose the interval (daily is a good
choice for a school). PiAssess then creates a backup by itself while running —
no one needs to remember it. The dashboard of the setting shows whether it is
active and when the last Drive upload happened.

### Connecting Google Drive (one-time, about 5 minutes)

1. Go to **console.cloud.google.com** and create a project (any name, e.g.
   *Pi World School Backups*).
2. In the project, open **APIs & Services → Library**, search for
   **Google Drive API** and click **Enable**.
3. Open **APIs & Services → Credentials → Create credentials → Service
   account**. Give it a name (e.g. *piassess-backup*) and finish.
4. Open the new service account → **Keys → Add key → Create JSON**. A `.json`
   key file downloads — keep it safe.
5. In **drive.google.com**, create a folder (e.g. *PiAssess Backups*), click
   **Share**, and add the service account's email (it looks like
   `piassess-backup@project.iam.gserviceaccount.com`) with the **Editor** role.
6. Back in PiAssess: upload the JSON key, paste the **folder ID** (the long
   code at the end of the folder's web address), press **Save Backup
   Settings**, then **Test connection** — it should show the folder's name.

From then on every backup (manual and automatic) is uploaded to that Drive
folder, so the data survives even if the school computer fails.

### Restoring

- **From a file** — choose the zip (a downloaded copy or one from a pen drive)
  and confirm. Restoring replaces *everything* currently in PiAssess with the
  backup's contents — including students, exams, results and settings — so it
  is normally only needed after a computer problem or when moving to a new
  computer. You may need to sign in again afterwards.
- **From Google Drive** — click **List Drive backups**, pick one, and restore
  or download it. This is how PiAssess is set up on a replacement computer.

---

## 8. Signing out

Use the menu under your name (top-right) → **Sign out**. Sessions also expire
automatically after 12 hours.

---

## 9. Something went wrong?

- **"Sign-in failed / too many attempts"** — wait one minute; the limit resets itself.
- **Import reports skipped rows** — correct the listed rows in your file and import again.
- **Any other problem** — note the message on screen and contact the administrator.
