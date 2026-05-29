import csv
import re
from pathlib import Path
from pypdf import PdfReader

BASE = Path(__file__).parent
CSV_IN = BASE / 'data' / 'courses.csv'
PDF_PATH = BASE / 'data' / 'courses.pdf'
CSV_OUT = BASE / 'data' / 'courses_enriched.csv'

# Read the existing clean course IDs/names
with CSV_IN.open('r', encoding='utf-8', newline='') as f:
    rows = list(csv.DictReader(f))

# Build a searchable text blob from the PDF
reader = PdfReader(str(PDF_PATH))
pdf_text = '\n'.join(page.extract_text() or '' for page in reader.pages)
pdf_text = pdf_text.replace('\r', '\n')
pdf_text = re.sub(r'[ \t]+', ' ', pdf_text)
pdf_text = re.sub(r'\n{2,}', '\n', pdf_text)

# Course type mapping from course code suffix
suffix_map = {
    'L': 'theory',
    'P': 'lab',
    'E': 'embedded',
    'J': 'project',
    'M': 'theory',  # online / MOOC-style courses; keep under theory for this list
}

section_starters = [
    'Foundation Core',
    'Discipline-linked Engineering Sciences',
    'Discipline Core',
    'Projects and Internship',
    'Open Elective',
    'Non-graded Core Requirement',
    'Bridge Course',
    'Specialization Elective',
]
section_regex = '|'.join(re.escape(x) for x in section_starters)

entries = []
missing_credits = []

for row in rows:
    code = row['course_id'].strip()
    name = row['course_name'].strip()

    # locate the code in the PDF and capture until the next course code or section heading
    match = re.search(
        rf'{re.escape(code)}\s+(.*?)(?=\n\d+\s+[A-Z]{{4}}\d{{3}}[A-Z]?|\n(?:{section_regex})\b|\Z)',
        pdf_text,
        re.S,
    )
    chunk = match.group(1) if match else ''
    chunk = re.sub(r'\s+', ' ', chunk).strip()

    # Extract the last decimal-looking number in the chunk as total credits
    credit_match = re.findall(r'(\d+\.\d+)', chunk)
    total_credits = credit_match[-1] if credit_match else ''

    # Clean up any obvious footer/text artifacts around the credits search
    if not total_credits:
        missing_credits.append(code)

    course_type = suffix_map.get(code[-1].upper(), 'other')

    entries.append({
        'course_id': code,
        'course_name': name,
        'course_type': course_type,
        'total_credits': total_credits,
    })

with CSV_OUT.open('w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['course_id', 'course_name', 'course_type', 'total_credits'])
    writer.writeheader()
    writer.writerows(entries)

print(f'Wrote {len(entries)} rows to {CSV_OUT.name}')
print(f'Missing credits for {len(missing_credits)} rows')
if missing_credits:
    print('First 20 missing:', ', '.join(missing_credits[:20]))
