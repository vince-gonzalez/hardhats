# student onboarding form for the classroom app
fields = ["student_email", "date_of_birth", "grade_level", "school", "parent_name"]
def save(student):
    require_verifiable_parental_consent(student)   # COPPA consent gate
    db.insert("students", student)
