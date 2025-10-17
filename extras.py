# Education & employment
    {"qid": "education", "text": "Highest level of education completed:", "type": "choice",
     "options": "Primary,Lower secondary,Upper secondary,Technical/Vocational,Bachelor,Master,Doctorate,Other", "required": "yes"},
    {"qid": "employment", "text": "Current employment status:", "type": "choice",
     "options": "Employed full-time,Employed part-time,Unemployed,Student,Self-employed,Other", "required": "no"},
    {"qid": "hours_work", "text": "If employed: average weekly working hours:", "type": "choice",
     "options": "0-10,11-20,21-30,31-40,41-50,50+", "required": "no"},

    # Household & income (use broad brackets for privacy)
    {"qid": "household_size", "text": "How many people live in your household (including you)?", "type": "choice",
     "options": "1,2,3,4,5,6,7+", "required": "yes"},
    {"qid": "household_children", "text": "How many children (under 18) live in your household?", "type": "choice",
     "options": "0,1,2,3,4+", "required": "no"},
    {"qid": "income_bracket", "text": "Approximate monthly household income (after tax):", "type": "choice",
     "options": "Prefer not to say, <1000, 1000-1999, 2000-2999, 3000-3999, 4000-4999, 5000+", "required": "no"},

    # Digital access
    {"qid": "internet_access", "text": "Do you have reliable internet access at home?", "type": "choice",
     "options": "Yes,No,Prefer not to say", "required": "no"},
    {"qid": "device_access", "text": "Which devices do you regularly use? (choose the most important)", "type": "choice",
     "options": "Smartphone,Laptop,Desktop,Tablet,Public/Shared computers,Other", "required": "no"},



python C:\Users\thiago-ext\Documents\FNIRS\psychopy\run_enem_blocks_3.py