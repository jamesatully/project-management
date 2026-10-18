"""
Fictitious permits and compliance milestones for the demo utility.

Each compliance unit gets the permit(s) it operates under, and each permit gets
milestones for its recurring reports (monthly, quarterly, annual, triennial)
from the start of the year two years back to a few months ahead, plus a few
one-off items. Past milestones are mostly submitted on time; where pm's
generator already filed the matching report (e.g. "Monthly Operating Report —
May 2026"), that document is the submittal and its date the submitted date.
A handful are left open past their due date, so some show as overdue.

Permit and milestone managers are utility compliance staff, added to the contact
directory here. The compliance manager holds the major treatment plant and water
system permits; specialists hold the rest and run day-to-day milestones.

Runs as an extension of ``pm.demo`` (registered at import, from
ComplianceConfig.ready()), with its own random stream so other data doesn't change.
"""
import calendar
import datetime
import random

from pm import demo as pm_demo
from pm.demo import UTILITY, UTILITY_DOMAIN, UTILITY_PHONE, add_months
from pm.models import ComplianceUnit, Contact, Document

from .models import ComplianceMilestone, Permit

CU = ComplianceUnit.UnitType
S = ComplianceMilestone.Status
P = Permit.Status
COMPLIANCE_ORG = f"{UTILITY} — Regulatory Compliance"
DEQ = "State Department of Environmental Quality"
HEALTH = "County Health Department — Drinking Water Program"
WATER_RESOURCES = "State Water Resources Department"

# Compliance staff: key -> (name, job title, role in organization).
STAFF = {
    "manager": ("Naomi Castellanos", "Regulatory Compliance Manager",
                "Leads the utility's permit compliance program: permit applications and renewals, agency "
                "correspondence and the compliance calendar."),
    "wastewater": ("Victor Ashby", "Wastewater Compliance Specialist",
                   "Prepares discharge monitoring reports, pretreatment reports and toxicity testing submittals "
                   "for the wastewater treatment plants."),
    "water": ("Ruth Okafor", "Water Quality Manager",
              "Manages drinking water sampling, monthly operating reports and the Consumer Confidence Report."),
    "resources": ("Jonah Pruitt", "Water Resources Planner",
                  "Tracks water rights and withdrawals and prepares water use and conservation reports."),
    "stormwater": ("Beatriz Solano", "Stormwater Program Coordinator",
                   "Runs the MS4 and industrial stormwater programs: inspections, monitoring and annual reports."),
    "environmental": ("Wesley Hollis", "Environmental Compliance Specialist",
                      "Coordinates biosolids, recycled water and storage tank compliance and inspections."),
}
# Unit types whose permits the compliance manager holds.
MAJOR_PERMIT_TYPES = {CU.WASTEWATER, CU.PUBLIC_WATER_SUPPLY}
UNIT_STAFF = {
    CU.WASTEWATER: "wastewater", CU.PUBLIC_WATER_SUPPLY: "water", CU.TANK: "environmental",
    CU.WATER_USE_PERMIT: "resources", CU.STORMWATER: "stormwater", CU.OTHER: "environmental",
}

# Milestone templates: (name, permit condition, schedule, due, matching document subject or None, description).
# Schedules and "due": monthly -> day of the following month; quarterly -> days after quarter end;
# annual -> (month, day) of the following year; triennial -> (month, day) of the inspection year.
# "{month}", "{year}" and "{q}" are filled in per occurrence.
DMR = ("Discharge Monitoring Report — {month}", "S1.A", "monthly", 28, "Discharge Monitoring Report — {month}",
       "Submit the monthly DMR with effluent flow, BOD, TSS, ammonia and bacteria results through the agency's "
       "electronic reporting system.")
WET = ("Whole Effluent Toxicity Test Results — Q{q} {year}", "S8.B", "quarterly", 45, None,
       "Submit the quarterly acute and chronic toxicity test results with the laboratory report.")
PRETREATMENT = ("Annual Pretreatment Program Report {year}", "S6.D", "annual", (3, 31),
                "Annual Pretreatment Program Report {year}",
                "Summarize industrial user inspections, sampling and enforcement for the calendar year.")
MOR = ("Monthly Operating Report — {month}", "4.1", "monthly", 28, "Monthly Operating Report — {month}",
       "Report daily production, disinfectant residuals and turbidity for the month to the Drinking Water Program.")
DBP = ("Disinfection Byproducts Monitoring — Q{q} {year}", "3.4", "quarterly", 10, None,
       "Submit quarterly TTHM and HAA5 results for each monitoring location.")
CCR = ("Consumer Confidence Report {year}", "4.2", "annual", (7, 1), "Consumer Confidence Report {year}",
       "Deliver the annual water quality report to customers and certify delivery to the Drinking Water Program.")
LEAD_COPPER = ("Lead and Copper Sampling Results {year}", "5.1", "annual", (3, 31),
               "Lead and Copper Sampling Results {year}",
               "Submit tap sampling results and the 90th percentile lead and copper levels.")
WATER_USE = ("Annual Water Use Report {year}", "C-7", "annual", (3, 31), "Annual Water Use Report {year}",
             "Report monthly withdrawals by source and compare them with the permitted annual allocation.")
WITHDRAWAL = ("Withdrawal and Water Level Report — Q{q} {year}", "C-9", "quarterly", 30, None,
              "Submit metered withdrawals and monitoring well water levels for the quarter.")
TANK = ("Storage Tank Inspection Report", "R-3", "triennial", (12, 31), "Storage Tank Inspection Report",
        "Inspect the reservoir interior and exterior (coatings, vents, hatches, sanitary defects) and submit the "
        "inspection report.")
MS4_ANNUAL = ("Stormwater Annual Report {year}", "S9.A", "annual", (3, 31), "Stormwater Annual Report {year}",
              "Report on each minimum control measure of the stormwater management program for the year.")
ISW_MONITORING = ("Stormwater Discharge Monitoring — Q{q} {year}", "S4.B", "quarterly", 45, None,
                  "Sample each outfall during a qualifying storm and submit results against benchmark values.")
BIOSOLIDS_ANNUAL = ("Annual Biosolids Report {year}", "B-12", "annual", (3, 31), "Annual Program Report {year}",
                    "Report biosolids quantities, quality and land application sites and agronomic rates.")
SOIL = ("Soil and Groundwater Monitoring — Q{q} {year}", "B-7", "quarterly", 30, None,
        "Sample soils and monitoring wells at active application sites and submit the results.")
RECYCLED_MONTHLY = ("Recycled Water Production Report — {month}", "R-5", "monthly", 20, None,
                    "Report recycled water produced and delivered, with turbidity and coliform results.")
RECYCLED_ANNUAL = ("Annual Recycled Water Report {year}", "R-11", "annual", (3, 31), "Annual Program Report {year}",
                   "Summarize recycled water use by customer, operational problems and cross-connection tests.")

# Permits by compliance unit: (permit name, number, agency, effective year offset, term years, templates).
# The effective year is relative to "today"; permits past expiration are administratively extended.
WW_TEMPLATES = [DMR, WET, PRETREATMENT]
PWS_TEMPLATES = [MOR, DBP, CCR, LEAD_COPPER]
PERMITS = {
    "Northwest Wastewater Treatment System": [
        ("Riverbend WWTP NPDES Permit", "RB-0021457", DEQ, -5, 5, WW_TEMPLATES),
    ],
    "South Valley Wastewater Reclamation System": [
        ("South Valley WRF NPDES Permit", "RB-0031822", DEQ, -3, 5, WW_TEMPLATES),
    ],
    "Eastgate Wastewater Treatment System": [
        ("Eastgate WWTP NPDES Permit", "RB-0044106", DEQ, -2, 5, WW_TEMPLATES),
    ],
    "Central Regional Potable Water System": [
        ("Central Regional Public Water System Operating Permit", "PWS 4100652", HEALTH, -4, 5, PWS_TEMPLATES),
    ],
    "North Fork Public Water System": [
        ("North Fork Public Water System Operating Permit", "PWS 4100718", HEALTH, -1, 5, PWS_TEMPLATES),
    ],
    "Riverbend Consolidated Water Use Permit": [
        ("Riverbend Consolidated Water Use Permit", "G-10475", WATER_RESOURCES, -6, 10, [WATER_USE, WITHDRAWAL]),
    ],
    "North Fork Wellfield Water Use Permit": [
        ("North Fork Wellfield Water Use Permit", "G-11902", WATER_RESOURCES, -3, 10, [WATER_USE, WITHDRAWAL]),
    ],
    "Municipal Separate Storm Sewer System (MS4)": [
        ("NPDES MS4 Phase II General Permit Coverage", "MS4-RB-0117", DEQ, -2, 5, [MS4_ANNUAL]),
    ],
    "Treatment Plant Industrial Stormwater Program": [
        ("Industrial Stormwater General Permit Coverage", "ISW-4471", DEQ, -3, 5, [MS4_ANNUAL, ISW_MONITORING]),
    ],
    "Biosolids Land Application Program": [
        ("Biosolids Land Application Permit", "BLA-0882", DEQ, -4, 10, [BIOSOLIDS_ANNUAL, SOIL]),
    ],
    "Recycled Water Distribution System": [
        ("Recycled Water Use Permit", "RW-0219", DEQ, -3, 10, [RECYCLED_MONTHLY, RECYCLED_ANNUAL]),
    ],
}
TANK_PERMIT = ("{name} Storage Tank Registration", "TR-{n}", HEALTH, -8, None, [TANK])

# One-off milestones: (unit, name, condition, days from today, status, staff key, description).
ONE_OFF = [
    ("Northwest Wastewater Treatment System", "Corrective Action Plan — Effluent Ammonia Exceedance", "S2.C", -9,
     S.IN_PROGRESS, "wastewater",
     "Submit a corrective action plan and schedule following the reported ammonia limit exceedance."),
    ("Northwest Wastewater Treatment System", "Outfall Diffuser Inspection Report", "S5.F", 64, S.NOT_STARTED,
     "wastewater", "Dive inspection of the outfall diffuser ports with video and a written condition report."),
    ("Municipal Separate Storm Sewer System (MS4)", "Stormwater Management Plan Update", "S5.A", 41,
     S.IN_PROGRESS, "stormwater", "Update the stormwater management plan for the new permit term and post it online."),
    ("North Fork Wellfield Water Use Permit", "Water Conservation Plan Update", "C-12", 212, S.NOT_STARTED,
     "resources", "Update the water conservation plan, including conservation targets and drought response stages."),
    ("Central Regional Potable Water System", "Sanitary Survey Deficiency Response", "6.3", -21, S.NOT_STARTED,
     "water", "Respond to the significant deficiencies identified in the sanitary survey with a correction schedule."),
]
# Renewal applications are due this many days before a permit expires.
RENEWAL_LEAD_DAYS = 180
TARGET_LEAD_DAYS = {"monthly": 7, "quarterly": 10, "annual": 30, "triennial": 45, "once": 14}


def quarter_end(year, q):
    month = q * 3
    return datetime.date(year, month, calendar.monthrange(year, month)[1])


class ComplianceGenerator:
    def __init__(self, generator):
        self.gen = generator
        self.today = generator.today
        self.rng = random.Random(generator.seed * 7919 + 13)
        self.start = datetime.date(self.today.year - 2, 1, 1)  # history kept from here
        self.milestones = []

    def make_staff(self):
        rng = random.Random(self.gen.seed * 7919 + 17)
        staff = {}
        for key, (name, title, role) in STAFF.items():
            staff[key] = Contact(
                name=name, title=title, organization=COMPLIANCE_ORG, contact_type=Contact.ContactType.INTERNAL,
                role_description=role, email=self.gen.email(name, UTILITY_DOMAIN),
                phone=f"{UTILITY_PHONE} ext. {rng.randint(500, 699)}",
            )
        Contact.objects.bulk_create(staff.values())
        return staff

    def occurrences(self, schedule, due, permit_docs):
        """(due date, format values, matching-document key) for each occurrence in the history window."""
        horizon = self.today + datetime.timedelta(days=100)
        if schedule == "monthly":
            month = add_months(self.start, -1)
            while True:
                due_date = add_months(month, 1).replace(day=due)
                if due_date > horizon:
                    return
                if due_date >= self.start:
                    yield due_date, {"month": f"{month:%B %Y}"}
                month = add_months(month, 1)
        elif schedule == "quarterly":
            for year in range(self.start.year - 1, self.today.year + 1):
                for q in range(1, 5):
                    due_date = quarter_end(year, q) + datetime.timedelta(days=due)
                    if self.start <= due_date <= horizon:
                        yield due_date, {"q": q, "year": year}
        elif schedule == "annual":
            for year in range(self.start.year - 1, self.today.year + 1):
                due_date = datetime.date(year + 1, *due)
                if self.start <= due_date <= self.today + datetime.timedelta(days=300):
                    yield due_date, {"year": year}
        elif schedule == "triennial":
            # Inspection years follow the unit's existing inspection reports (pm files one every three years).
            years = sorted(d.document_date.year for d in permit_docs.get("triennial", []))
            year = years[0] if years else self.start.year
            while year <= self.today.year + 1:
                due_date = datetime.date(year, *due)
                if due_date >= self.start:
                    yield due_date, {"year": year}
                year += 3

    def progress(self, due_date, schedule, document=None):
        """Status and submitted date for an occurrence, as of today."""
        today = self.today
        if document is not None:
            submitted = document.document_date
        elif due_date < today:
            if due_date > today - datetime.timedelta(days=45) and self.rng.random() < 0.15:
                return self.rng.choice([S.NOT_STARTED, S.IN_PROGRESS]), None  # left open: overdue
            if self.rng.random() < 0.05:
                submitted = due_date + datetime.timedelta(days=self.rng.randint(1, 20))  # late
            else:
                submitted = due_date - datetime.timedelta(days=self.rng.randint(0, TARGET_LEAD_DAYS[schedule]))
            submitted = min(submitted, today)
        elif due_date <= today + datetime.timedelta(days=45):
            if self.rng.random() < 0.1 and due_date - datetime.timedelta(days=10) <= today:
                submitted = today - datetime.timedelta(days=self.rng.randint(0, 3))  # in early
            else:
                return (S.IN_PROGRESS if self.rng.random() < 0.7 else S.NOT_STARTED), None
        else:
            return S.NOT_STARTED, None
        return (S.SUBMITTED if submitted > today - datetime.timedelta(days=30) else S.COMPLETE), submitted

    def add(self, permit, manager, name, condition, due_date, schedule, description, document=None, status=None):
        if status is None:
            status, submitted = self.progress(due_date, schedule, document)
        else:
            submitted = None
        self.milestones.append(ComplianceMilestone(
            permit=permit, manager=manager, name=name, permit_condition=condition, due_date=due_date,
            target_date=due_date - datetime.timedelta(days=TARGET_LEAD_DAYS[schedule]), status=status,
            submitted_date=submitted, submittal_document=document if submitted else None, description=description,
        ))

    def unit_documents(self, unit):
        """The unit's own compliance records, by subject (triennial inspection reports grouped)."""
        docs = {}
        for doc in Document.objects.filter(compliance_unit=unit, project__isnull=True).order_by("document_date"):
            docs[doc.subject] = doc
            if doc.subject == TANK[4]:
                docs.setdefault("triennial", []).append(doc)
        return docs

    def run(self):
        staff = self.make_staff()
        units = self.gen.units
        permits = []
        tank_number = 3301
        for unit in units.values():
            specs = PERMITS.get(unit.name)
            if unit.unit_type == CU.TANK:
                name, number, agency, offset, term, templates = TANK_PERMIT
                specs = [(name.format(name=unit.name), number.format(n=tank_number), agency, offset, term, templates)]
                tank_number += 1
            docs = self.unit_documents(unit)
            manager = staff[UNIT_STAFF[unit.unit_type]]
            permit_manager = staff["manager"] if unit.unit_type in MAJOR_PERMIT_TYPES else manager
            for name, number, agency, offset, term, templates in specs:
                effective = datetime.date(self.today.year + offset, self.rng.choice([1, 4, 7, 10]), 1)
                expiration = effective.replace(year=effective.year + term) - datetime.timedelta(days=1) if term else None
                status = P.EXTENDED if expiration and expiration < self.today else P.ACTIVE
                permit = Permit(
                    compliance_unit=unit, name=name, permit_number=number, issuing_agency=agency,
                    manager=permit_manager, status=status,
                    effective_date=effective, expiration_date=expiration,
                    description=f"Issued by the {agency} for the {unit.name}." if not term else
                    f"{term}-year permit issued by the {agency} for the {unit.name}.",
                )
                permits.append(permit)
                for title, condition, schedule, due, doc_subject, description in templates:
                    for due_date, values in self.occurrences(schedule, due, docs):
                        if due_date < effective:  # earlier ones belong to the previous permit term
                            continue
                        document = None
                        if schedule == "triennial":
                            document = next((d for d in docs.get("triennial", [])
                                             if d.document_date.year == due_date.year), None)
                        elif doc_subject:
                            document = docs.get(doc_subject.format(**values))
                        self.add(permit, manager, title.format(**values), condition, due_date, schedule, description,
                                 document)
                if expiration:  # renewal application, due ahead of expiration
                    renewal_due = expiration - datetime.timedelta(days=RENEWAL_LEAD_DAYS)
                    if self.start <= renewal_due <= self.today + datetime.timedelta(days=400):
                        self.add(permit, staff["manager"], "Permit Renewal Application", "G4", renewal_due, "once",
                                 f"Submit a complete renewal application to the {agency} at least "
                                 f"{RENEWAL_LEAD_DAYS} days before the permit expires.")
        Permit.objects.bulk_create(permits)

        by_unit = {p.compliance_unit.name: p for p in permits}
        for unit_name, name, condition, days, status, staff_key, description in ONE_OFF:
            due_date = self.today + datetime.timedelta(days=days)
            self.add(by_unit[unit_name], staff[staff_key], name, condition, due_date, "once", description, status=status)

        for m in self.milestones:
            m.full_clean()
        ComplianceMilestone.objects.bulk_create(self.milestones, batch_size=500)
        self.gen.backdate(ComplianceMilestone, self.milestones,
                          [m.due_date - datetime.timedelta(days=60) for m in self.milestones])
        return {"permits": len(permits), "compliance milestones": len(self.milestones)}


def extend(generator, plans):
    return ComplianceGenerator(generator).run()


pm_demo.EXTENSIONS.append(extend)
pm_demo.FLUSH_FIRST.extend([ComplianceMilestone, Permit])
