"""
Fictitious demo data for a water / wastewater utility.

Everything here is invented: the utility ("Riverbend Water & Sewer Utility"),
people, vendors, addresses (``.example`` domains, 555-01xx phone numbers),
projects and dollar amounts. Generation is deterministic for a given seed and
reference date, so ``manage.py seed_demo`` reproduces the same dataset.

Use :func:`generate` (called by the ``seed_demo`` management command).
"""
import datetime
import random
from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone

from .models import Document, FieldReport, Invoice, Project, PurchaseOrder, Vendor

UTILITY = "Riverbend Water & Sewer Utility"

PROJECT_MANAGERS = [
    "Dana Whitfield", "Luis Ortega", "Priya Raman", "Marcus Bell", "Erin Kowalski",
    "Tomás Herrera", "Grace Nakamura", "Owen Fitzgerald", "Aisha Mensah", "Caleb Lindqvist",
]
INSPECTORS = ["Ray Delgado", "Monica Tran", "Hank Petersen", "Sofia Alvarez", "Derek Osei", "Jill Moreau"]

STREETS = [
    "Oak Street", "Maple Avenue", "Riverside Drive", "Harbor Boulevard", "Cedar Lane", "Elm Street",
    "Willow Road", "Summit Avenue", "Kingsley Road", "Granite Way", "Mill Street", "Lakeview Drive",
    "Pioneer Parkway", "Juniper Court", "Bayshore Road", "Founders Avenue", "Alder Street", "Ridgecrest Drive",
    "Canal Street", "Orchard Lane", "Beacon Street", "Hawthorne Avenue", "Sycamore Drive", "Railroad Avenue",
]
AREAS = ["Northside", "Eastgate", "Mill Creek", "West Hills", "Old Town", "Southport", "Ferry Point", "Brookfield",
         "Highland Park", "Lower Valley", "Sunset Terrace", "Pine Ridge"]
WATER_PLANTS = ["Cedar Point WTP", "North Fork WTP"]
WW_PLANTS = ["Riverbend WWTP", "South Valley WRF", "Eastgate WWTP"]
CREEKS = ["Bear Creek", "Willow Creek", "Salmon Run", "Cottonwood Creek", "Little Fork", "Heron Slough"]
SUBDIVISIONS = ["Willow Ridge", "Stonebrook Estates", "Aspen Meadows", "Harbor Heights", "Copper Hill",
                "Quail Hollow", "Lakeshore Commons", "Prairie Crossing"]
BUSINESS_PARKS = ["Gateway Business Park", "Riverbend Logistics Center", "Northpoint Tech Campus", "Eastgate Commerce Center"]
RESERVOIRS = ["Hilltop", "Summit", "Ridgeview", "Crestline", "Pinecrest", "Valley View"]
BASINS = ["Basin A", "Basin C", "Basin F", "Mill Creek Basin", "Northside Basin", "Old Town Basin"]

# Project templates by category: (template, needs construction?)
CATEGORIES = {
    "water_main": {
        "count": 18, "type": Project.ProjectType.CIP, "budgets": ["6822015", "6822016", "6822031"],
        "construction": (800_000, 6_000_000),
        "names": [
            "{street} Water Main Replacement", "{area} Distribution Main Upgrade — Phase {n}",
            "{street} 16-inch Transmission Main", "{area} Cast Iron Main Replacement",
            "{street} Water Main and Service Renewal",
        ],
    },
    "sewer": {
        "count": 18, "type": Project.ProjectType.CIP, "budgets": ["6833010", "6833011", "6833027"],
        "construction": (400_000, 4_500_000),
        "names": [
            "{street} Sanitary Sewer Rehabilitation", "{area} Trunk Sewer CIPP Lining",
            "Lift Station {k} Replacement", "{area} Force Main Replacement",
            "{basin} Manhole Rehabilitation", "{street} Sewer Capacity Upgrade",
        ],
    },
    "plant": {
        "count": 18, "type": Project.ProjectType.CIP, "budgets": ["6844001", "6844002", "6844019"],
        "construction": (1_500_000, 24_000_000),
        "names": [
            "{wwtp} Aeration System Upgrade", "{wwtp} Headworks Screening Improvements",
            "{wwtp} Digester No. {k} Rehabilitation", "{wwtp} UV Disinfection Replacement",
            "{wwtp} Secondary Clarifier Rehabilitation", "{wtp} Filter Underdrain Replacement",
            "{wtp} Ozone System Replacement", "{wtp} Clearwell Seismic Retrofit",
            "{plant} Electrical Switchgear Replacement", "{plant} SCADA Modernization",
        ],
    },
    "storage": {
        "count": 10, "type": Project.ProjectType.CIP, "budgets": ["6822040", "6822041"],
        "construction": (500_000, 5_000_000),
        "names": [
            "{reservoir} Reservoir Recoating", "{reservoir} Elevated Tank Rehabilitation",
            "{reservoir} Booster Pump Station Replacement", "Well No. {k} Rehabilitation",
            "Well Field {k} PFAS Treatment",
        ],
    },
    "study": {
        "count": 14, "type": Project.ProjectType.CIP, "budgets": ["6850100", "6850101"],
        "construction": None,
        "names": [
            "Water System Master Plan Update", "Sewer Collection System Hydraulic Model Update",
            "Inflow & Infiltration Study — {basin}", "Biosolids Management Plan",
            "Linear Asset Condition Assessment", "Lead Service Line Inventory",
            "Risk and Resilience Assessment", "Water and Sewer Rate Study",
            "Nutrient Removal Feasibility Study — {wwtp}", "Corrosion Control Treatment Study",
            "Wastewater Facilities Plan", "Water Loss Audit and AMI Business Case",
            "Pump Station Energy Efficiency Study", "Recycled Water Feasibility Study",
        ],
    },
    "environmental": {
        "count": 12, "type": Project.ProjectType.ENVIRONMENTAL, "budgets": ["6860020", "6860021"],
        "construction": (200_000, 2_000_000),
        "names": [
            "{creek} Outfall Stream Restoration", "{creek} Wetland Mitigation Monitoring",
            "NPDES Permit Renewal Support — {wwtp}", "Groundwater Monitoring Program — {wwtp}",
            "{creek} Sanitary Sewer Overflow Remediation", "Riparian Buffer Restoration at {wwtp}",
            "{creek} Fish Passage Improvements", "Source Water Protection Plan",
        ],
    },
    "development": {
        "count": 10, "type": Project.ProjectType.DEVELOPMENT, "budgets": ["6870001"],
        "construction": None,
        "names": [
            "{subdivision} Water and Sewer Extension", "{subdivision} Developer Lift Station Acceptance",
            "{park} Utility Extension", "{subdivision} Main Extension Plan Review",
        ],
    },
}

# (name, category). Categories: engineering, contractor, environmental, lab, supplier.
VENDORS = [
    ("Bluewater Engineering Group", "engineering"), ("Hydrocrest Consulting Engineers", "engineering"),
    ("Clearline Civil Partners", "engineering"), ("Northgate Water Engineers", "engineering"),
    ("Meridian Infrastructure Design", "engineering"), ("Stillwater Process Engineering", "engineering"),
    ("Keystone Utility Engineers", "engineering"), ("Arbor & Finch Engineering", "engineering"),
    ("Tidewater Systems Engineering", "engineering"), ("Summit Hydraulics Inc.", "engineering"),
    ("Cobalt Ridge Engineering", "engineering"), ("Pinnacle Water Resources", "engineering"),
    ("Vantage Construction Management", "engineering"), ("Lindmark Inspection Services", "engineering"),
    ("Granite Ridge Contractors", "contractor"), ("Ironwood Pipeline Co.", "contractor"),
    ("Redstone Underground", "contractor"), ("Bayside Civil Constructors", "contractor"),
    ("Hartwell & Sons Excavating", "contractor"), ("Trident Treatment Builders", "contractor"),
    ("Cascade Pipe Renewal", "contractor"), ("Keel Mechanical Contractors", "contractor"),
    ("Stonefield Heavy Civil", "contractor"), ("Ridgeway Electrical Contractors", "contractor"),
    ("Coastline Coatings Inc.", "contractor"), ("Ember Valley Construction", "contractor"),
    ("Northstar Trenchless", "contractor"), ("Quarry Point Builders", "contractor"),
    ("Silverline Tank Services", "contractor"), ("Atlas Pump & Well", "contractor"),
    ("Verdant Ecological Consulting", "environmental"), ("Fernbrook Environmental", "environmental"),
    ("Riparian Works LLC", "environmental"), ("Kestrel Environmental Services", "environmental"),
    ("Tributary Science Group", "environmental"), ("Greenmarsh Restoration", "environmental"),
    ("Basalt Geotechnical", "lab"), ("Precision Materials Testing", "lab"),
    ("Aquatrace Analytical Labs", "lab"), ("Benchmark Survey & Mapping", "lab"),
    ("Delta Pipe & Supply", "supplier"), ("Rivermark Valve Supply", "supplier"),
    ("Clarion Chemical Distributors", "supplier"), ("MeterPoint Systems", "supplier"),
    ("Frontier Pump Supply", "supplier"), ("Halcyon Process Equipment", "supplier"),
    ("Brightwell Electrical Supply", "supplier"), ("Westfork Fleet & Equipment", "supplier"),
    ("Polaris Controls Integration", "contractor"), ("Sagebrush Landscape Restoration", "environmental"),
]
CITIES = [("Riverbend", "OR", "97401"), ("Cedar Falls", "WA", "98101"), ("Millbrook", "OR", "97035"),
          ("Port Halden", "WA", "98402"), ("Ashford", "ID", "83702"), ("Lakemont", "CA", "95814")]
FIRST = ["Kim", "Jordan", "Alex", "Morgan", "Taylor", "Casey", "Riley", "Jamie", "Avery", "Quinn", "Drew", "Reese",
         "Harper", "Rowan", "Emerson", "Skyler", "Parker", "Sasha", "Devon", "Robin"]
LAST = ["Lo", "Okafor", "Brennan", "Castillo", "Hughes", "Novak", "Sato", "Abernathy", "Lindgren", "Patel", "Dubois",
        "Marsh", "Kaur", "Whitaker", "Ferreira", "Yoon", "Gallagher", "Mbeki", "Larsen", "Ibarra"]

# Blanket (non-project) purchase orders for operations.
BLANKET_POS = [
    ("supplier", "Sodium hypochlorite supply", 180_000), ("supplier", "Ferric chloride supply", 140_000),
    ("supplier", "AMI meters and endpoints", 450_000), ("supplier", "Ductile iron pipe and fittings", 260_000),
    ("supplier", "Valves and hydrant repair parts", 120_000), ("lab", "Compliance laboratory testing", 95_000),
    ("lab", "Biosolids analytical services", 60_000), ("engineering", "On-call engineering services", 300_000),
    ("environmental", "On-call environmental permitting", 150_000), ("contractor", "On-call emergency main repair", 500_000),
    ("supplier", "Pump repair parts", 85_000), ("supplier", "Process instrumentation", 110_000),
]

OBSERVATIONS = {
    "water_main": [
        "Contractor installed {n} LF of 12-inch DIP along {street}; bedding and backfill compaction witnessed.",
        "Hydrostatic pressure test of segment {k} passed at 150 psi for 2 hours.",
        "Service reconnections completed at {k} residences; customers notified 48 hours in advance.",
        "Tapping sleeve and valve installed on existing 8-inch main; shutdown lasted {k} hours.",
        "Temporary trench paving placed between stations {k}+00 and {k2}+50.",
        "Bacteriological samples collected from new main; awaiting lab results before tie-in.",
    ],
    "sewer": [
        "CIPP liner installed from MH-{k} to MH-{k2} ({n} LF); post-lining CCTV scheduled.",
        "Bypass pumping operating at MH-{k}; no overflows observed during shift.",
        "Lateral reinstatements completed ({k} of {k2}); two require robotic trimming.",
        "Wet well coating inspected; holiday testing found minor pinholes to be repaired.",
        "Manhole MH-{k} rehabilitated with cementitious liner; frame and cover reset to grade.",
        "Mandrel and air testing of new sewer reach passed.",
    ],
    "plant": [
        "Contractor set new blower No. {k} on pad; anchor bolts torqued and witnessed.",
        "Concrete placed for basin wall section {k}; slump and cylinder samples taken by testing lab.",
        "Electrical crew pulling conductors to MCC-{k}; conduit fill verified against drawings.",
        "Manufacturer's representative on site for startup testing of new equipment.",
        "Existing process unit taken offline per approved shutdown plan; plant effluent remained in compliance.",
        "Instrumentation loop checks completed for {k} of {k2} devices.",
    ],
    "storage": [
        "Abrasive blasting of tank interior approximately {pct}% complete; containment intact.",
        "Coating dry film thickness readings taken; average {k} mils, within specification.",
        "Pump No. {k} installed; laser alignment checked and recorded.",
        "Disinfection of reservoir per AWWA C652 underway; sampling planned for tomorrow.",
        "Well rehabilitation: brushing and bailing of screen interval completed.",
    ],
    "study": [
        "Field crew completed condition assessment of {k} manholes in the study area.",
        "Temporary flow meters checked at {k} locations; data download successful.",
        "Hydrant flow tests performed at {k} hydrants to calibrate the hydraulic model.",
        "Potholed {k} service lines to verify material; results logged in inventory.",
    ],
    "environmental": [
        "Planted {n} native trees and shrubs along the restored channel.",
        "Erosion control matting installed on east bank; silt fence intact.",
        "Biologist completed monitoring transects; vegetation survival estimated at {pct}%.",
        "Turbidity readings upstream and downstream within permit limits.",
        "Removed {k} cubic yards of debris from outfall channel.",
        "Groundwater samples collected from {k} monitoring wells.",
    ],
    "development": [
        "Witnessed pressure testing and bacteriological sampling of new mains.",
        "Inspected sewer main installation; mandrel test passed.",
        "Final walk-through with developer; punch list of {k} items issued.",
        "Verified valve box and hydrant locations against approved plans.",
    ],
}
SAFETY = [
    "Tailgate safety meeting held; topic: trench shoring and protective systems.",
    "Confined space entry permit reviewed; continuous atmospheric monitoring in place.",
    "Traffic control set up per approved plan; flaggers on site at both ends.",
    "No incidents or near misses reported.",
    "Observed one worker without hard hat in work zone; corrected immediately.",
    "Excavation deeper than 5 ft; trench box in use and inspected by competent person.",
    "Heat illness prevention measures in place: water, shade and scheduled breaks.",
    "Hot work permit issued for welding; fire watch assigned.",
    "Lockout/tagout verified on equipment before work began.",
]
WEATHER = {
    "winter": ["Overcast, 38°F, light rain in afternoon.", "Cold and clear, 31°F at start of shift; frost on site.",
               "Steady rain, 42°F; work paused for 1 hour.", "Fog early, clearing by noon, 45°F."],
    "spring": ["Partly cloudy, 58°F.", "Showers in morning, 54°F; site muddy.", "Sunny, 63°F, light wind."],
    "summer": ["Clear and hot, 91°F.", "Sunny, 84°F, light breeze.", "Hazy, 88°F; air quality advisory in effect."],
    "fall": ["Cloudy, 55°F.", "Windy, 50°F, scattered showers.", "Clear and cool, 48°F."],
}
SEASON = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
          6: "summer", 7: "summer", 8: "summer", 9: "fall", 10: "fall", 11: "fall"}

DOC_SUBJECTS = {
    Document.DocumentType.LETTER: ["Notice of Award", "Notice to Proceed", "Request for Time Extension",
                                   "Notice of Substantial Completion", "Final Acceptance"],
    Document.DocumentType.MEMO: ["30% Design Review Comments", "60% Design Review Comments", "90% Design Review Comments",
                                 "Budget Status Update", "Scope Change Recommendation"],
    Document.DocumentType.EMAIL: ["Shutdown Coordination", "Schedule Update Request", "Customer Complaint Follow-up",
                                  "Access Agreement Status"],
    Document.DocumentType.RFI: ["Conflict with Existing Gas Line", "Valve Box Detail Clarification",
                                "Coating System Substitution", "Pipe Bedding Material", "Electrical Conduit Routing",
                                "Existing Utility Depth Discrepancy"],
    Document.DocumentType.SUBMITTAL: ["Ductile Iron Pipe", "Gate Valves", "Traffic Control Plan", "Blower Equipment",
                                      "Coating System", "Bypass Pumping Plan", "Concrete Mix Design"],
    Document.DocumentType.CHANGE_ORDER: ["Unforeseen Rock Excavation", "Additional Service Reconnections",
                                         "Revised Electrical Scope", "Contaminated Soil Handling"],
    Document.DocumentType.MEETING_MINUTES: ["Design Kickoff Meeting", "Preconstruction Meeting", "Progress Meeting",
                                            "Stakeholder Workshop"],
    Document.DocumentType.REPORT: ["Geotechnical Investigation Report", "Basis of Design Report",
                                   "Condition Assessment Report", "Draft Final Report", "Monthly Progress Report"],
    Document.DocumentType.DRAWING: ["90% Design Drawings", "Issued for Construction Drawings", "Record Drawings"],
}
AGENCIES = ["State Department of Environmental Quality", "County Health Department — Drinking Water Program",
            "City of Riverbend Planning Department", "County Public Works", "State Fish and Wildlife Agency"]


@dataclass
class Plan:
    """In-memory bookkeeping for one project while generating its records."""

    project: Project
    category: str
    start: datetime.date
    design_vendor: Vendor = None
    contractor: Vendor = None
    construction_start: datetime.date = None
    construction_end: datetime.date = None


def add_months(d, months):
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    return datetime.date(year, month, min(d.day, 28))


def money(value):
    """Round to a plausible contract figure."""
    step = 1000 if value > 100_000 else 100
    return Decimal(int(round(value / step)) * step).quantize(Decimal("0.01"))


# Callables ``fn(generator, plans) -> {label: count}`` run after the core data is
# created; other apps (e.g. planning) append to this from AppConfig.ready().
EXTENSIONS = []


class Generator:
    def __init__(self, seed=42, today=None, project_count=100):
        self.seed = seed
        self.rng = random.Random(seed)
        self.today = today or datetime.date.today()
        self.project_count = project_count
        self.vendors = {}
        self.po_seq = 4500100
        self.invoice_seq = {}

    # -- helpers ---------------------------------------------------------------
    def pick(self, seq):
        return self.rng.choice(seq)

    def fill(self, template):
        r = self.rng
        return template.format(
            street=self.pick(STREETS), area=self.pick(AREAS), basin=self.pick(BASINS), wwtp=self.pick(WW_PLANTS),
            wtp=self.pick(WATER_PLANTS), plant=self.pick(WW_PLANTS + WATER_PLANTS), creek=self.pick(CREEKS),
            subdivision=self.pick(SUBDIVISIONS), park=self.pick(BUSINESS_PARKS), reservoir=self.pick(RESERVOIRS),
            n=r.randint(1, 4) if "Phase" in template else r.randint(80, 1400), k=r.randint(1, 24),
            k2=r.randint(25, 60), pct=r.randint(55, 95),
        )

    def date_between(self, start, end):
        if end <= start:
            return start
        return start + datetime.timedelta(days=self.rng.randint(0, (end - start).days))

    # -- vendors ---------------------------------------------------------------
    def make_vendors(self):
        objs = []
        for i, (name, category) in enumerate(VENDORS):
            city, state, zip_code = self.pick(CITIES)
            slug = "".join(c for c in name.lower().replace("&", "and").replace(" ", "-") if c.isalnum() or c == "-")
            vendor = Vendor(
                name=name,
                mailing_address=f"{self.rng.randint(100, 9800)} {self.pick(STREETS)}\n{city}, {state} {zip_code}",
                website=f"https://www.{slug.strip('-').replace('--', '-')}.example",
                primary_contact_name=f"{self.pick(FIRST)} {self.pick(LAST)}",
                primary_contact_phone=f"(503) 555-{100 + i:04d}",
            )
            vendor.category = category
            objs.append(vendor)
        Vendor.objects.bulk_create(objs)
        for v in objs:
            self.vendors.setdefault(v.category, []).append(v)
        return objs

    # -- projects --------------------------------------------------------------
    def status_for(self, start, category):
        age = (self.today - start).days / 365
        S = Project.Status
        if age >= 4:
            weights = {S.COMPLETE: 72, S.CONSTRUCTION: 12, S.ON_HOLD: 8, S.CANCELLED: 8}
        elif age >= 2:
            weights = {S.COMPLETE: 30, S.CONSTRUCTION: 42, S.DESIGN: 16, S.ON_HOLD: 6, S.CANCELLED: 6}
        elif age >= 0.75:
            weights = {S.CONSTRUCTION: 30, S.DESIGN: 45, S.PLANNING: 15, S.ON_HOLD: 10}
        else:
            weights = {S.PLANNING: 60, S.DESIGN: 40}
        if CATEGORIES[category]["construction"] is None and category != "development":
            # Studies have no construction phase: "Design" means the study is under way.
            weights[S.DESIGN] = weights.get(S.DESIGN, 0) + weights.pop(S.CONSTRUCTION, 0)
        return self.rng.choices(list(weights), weights=list(weights.values()))[0]

    def make_projects(self):
        total = sum(c["count"] for c in CATEGORIES.values())
        plans, used_ids, used_names = [], set(), set()
        # Deal PMs from a shuffled deck so workloads are uneven but realistic (roughly 7-13 projects each).
        pm_deck = [pm for pm in PROJECT_MANAGERS for _ in range(self.rng.randint(7, 13) * self.project_count // 100 + 1)]
        self.rng.shuffle(pm_deck)
        for category, spec in CATEGORIES.items():
            count = round(spec["count"] * self.project_count / total)
            for _ in range(count):
                for _attempt in range(50):
                    name = self.fill(self.pick(spec["names"]))
                    if name not in used_names:
                        break
                used_names.add(name)
                start = self.date_between(datetime.date(2018, 1, 1), self.today - datetime.timedelta(days=20))
                while True:
                    pid = f"{start.year}-{self.rng.randint(1, 4)}-{self.rng.randint(1, 60)}-{self.rng.choice([0, 0, 0, 1, 2])}"
                    if pid not in used_ids:
                        used_ids.add(pid)
                        break
                project = Project(
                    name=name,
                    project_id=pid,
                    budget_id=self.pick(spec["budgets"]),
                    project_type=spec["type"],
                    status=self.status_for(start, category),
                    project_manager=pm_deck.pop() if pm_deck else self.pick(PROJECT_MANAGERS),
                )
                plans.append(Plan(project=project, category=category, start=start))
        for p in plans:
            p.project.full_clean()
        Project.objects.bulk_create([p.project for p in plans])
        self.backdate(Project, [p.project for p in plans], [p.start for p in plans])
        return plans

    # -- purchase orders -------------------------------------------------------
    def new_po(self, vendor, amount, start, end, status, project=None, contract=True):
        self.po_seq += self.rng.randint(1, 9)
        return PurchaseOrder(
            po_number=str(self.po_seq),
            status=status,
            amount=money(amount),
            vendor=vendor,
            project=project,
            contract_number=f"C-{start.year}-{self.rng.randint(10, 299):03d}" if contract else "",
            start_date=start,
            end_date=end,
        )

    def po_status(self, start, end, project_status):
        PS, S = PurchaseOrder.Status, Project.Status
        if project_status == S.CANCELLED:
            return self.rng.choice([PS.CANCELLED, PS.CLOSED])
        if start > self.today:
            return PS.DRAFT
        if end < self.today or project_status == S.COMPLETE:
            return PS.CLOSED
        return PS.OPEN

    def make_purchase_orders(self, plans):
        pos = []
        S = Project.Status
        for plan in plans:
            project, spec, status = plan.project, CATEGORIES[plan.category], plan.project.status
            if status == S.PLANNING and self.rng.random() < 0.6:
                continue  # many planning-stage projects have no POs yet
            if plan.category == "development":
                if self.rng.random() < 0.5:  # developer-funded; utility hires a plan reviewer on some
                    end = add_months(plan.start, self.rng.randint(4, 10))
                    pos.append(self.new_po(self.pick(self.vendors["engineering"]), self.rng.uniform(8_000, 60_000),
                                           plan.start, end, self.po_status(plan.start, end, status), project))
                continue

            design_category = "environmental" if plan.category == "environmental" else "engineering"
            plan.design_vendor = self.pick(self.vendors[design_category])
            const_range = spec["construction"]
            if const_range:
                const_value = self.rng.uniform(*const_range)
                design_value = const_value * self.rng.uniform(0.07, 0.13)
            else:
                design_value = self.rng.uniform(60_000, 650_000)
            design_end = add_months(plan.start, self.rng.randint(8, 22))
            design_status = (PurchaseOrder.Status.DRAFT if status == S.PLANNING
                             else self.po_status(plan.start, design_end, status))
            if status in (S.DESIGN, S.ON_HOLD) and design_status == PurchaseOrder.Status.CLOSED:
                design_status = PurchaseOrder.Status.OPEN  # design still running past original end date
                design_end = add_months(self.today, self.rng.randint(2, 9))
            pos.append(self.new_po(plan.design_vendor, design_value, plan.start, design_end, design_status, project))

            if const_range and status in (S.CONSTRUCTION, S.COMPLETE):
                plan.contractor = self.pick(self.vendors["contractor"] if plan.category != "environmental"
                                            else self.vendors["environmental"] + self.vendors["contractor"][:3])
                plan.construction_start = min(add_months(design_end, self.rng.randint(1, 4)),
                                              self.today - datetime.timedelta(days=self.rng.randint(30, 200)))
                duration = self.rng.randint(6, 30 if plan.category == "plant" else 18)
                plan.construction_end = add_months(plan.construction_start, duration)
                if status == S.COMPLETE:
                    plan.construction_end = min(plan.construction_end, self.today - datetime.timedelta(days=30))
                elif plan.construction_end < self.today:
                    plan.construction_end = add_months(self.today, self.rng.randint(1, 8))
                c_status = self.po_status(plan.construction_start, plan.construction_end, status)
                pos.append(self.new_po(plan.contractor, const_value, plan.construction_start,
                                       plan.construction_end, c_status, project))
                # Construction management / inspection and materials testing.
                cm_vendor = self.pick([v for v in self.vendors["engineering"] if v != plan.design_vendor])
                pos.append(self.new_po(cm_vendor, const_value * self.rng.uniform(0.05, 0.09), plan.construction_start,
                                       plan.construction_end, c_status, project))
                if self.rng.random() < 0.6:
                    pos.append(self.new_po(self.pick(self.vendors["lab"]), self.rng.uniform(15_000, 120_000),
                                           plan.construction_start, plan.construction_end, c_status, project,
                                           contract=False))
            elif self.rng.random() < 0.25 and status != S.PLANNING:
                # Geotech / survey support during design.
                pos.append(self.new_po(self.pick(self.vendors["lab"]), self.rng.uniform(12_000, 90_000),
                                       plan.start, design_end, design_status, project, contract=False))

        for category, description, value in BLANKET_POS:
            start = datetime.date(self.today.year - self.rng.choice([0, 1]), 7, 1)
            end = add_months(start, 12) - datetime.timedelta(days=1)
            po = self.new_po(self.pick(self.vendors[category]), value * self.rng.uniform(0.8, 1.3), start, end,
                             self.po_status(start, end, None))
            po.contract_number = f"BPO-{start.year}-{self.rng.randint(1, 40):02d}"
            pos.append(po)

        for po in pos:
            po.full_clean(validate_unique=False)
        PurchaseOrder.objects.bulk_create(pos)
        self.backdate(PurchaseOrder, pos, [po.start_date - datetime.timedelta(days=self.rng.randint(5, 30)) for po in pos])
        return pos

    # -- invoices --------------------------------------------------------------
    def invoice_number(self, vendor):
        prefix = "".join(w[0] for w in vendor.name.replace("&", "").split()[:3]).upper()
        seq = self.invoice_seq.setdefault(vendor.pk, self.rng.randint(1000, 4000))
        self.invoice_seq[vendor.pk] = seq + 1
        return f"{prefix}-{seq}"

    def make_invoices(self, pos):
        invoices = []
        IS, PS = Invoice.Status, PurchaseOrder.Status
        for po in pos:
            if po.status not in (PS.OPEN, PS.CLOSED, PS.CANCELLED) or po.start_date >= self.today:
                continue
            # Bill monthly for at most three years; on-hold projects stopped billing partway through.
            last = min(po.end_date, self.today, add_months(po.start_date, 36))
            if po.project and po.project.status == Project.Status.ON_HOLD:
                last = self.date_between(min(add_months(po.start_date, 3), last), last)
            months = []
            d = add_months(po.start_date, 1)
            while d <= last:
                months.append(d)
                d = add_months(d, 1)
            if not months:
                continue
            if po.status == PS.CANCELLED:
                months = months[: self.rng.randint(0, 3)]
                if not months:
                    continue
            # Share of the PO billed so far.
            if po.status == PS.CLOSED:
                share = self.rng.uniform(1.02, 1.14) if self.rng.random() < 0.07 else self.rng.uniform(0.86, 1.0)
            elif po.status == PS.CANCELLED:
                share = self.rng.uniform(0.05, 0.25)
            else:
                elapsed = (self.today - po.start_date).days / max((po.end_date - po.start_date).days, 1)
                share = min(elapsed, 1) * self.rng.uniform(0.75, 1.0)
                if self.rng.random() < 0.05:
                    share = self.rng.uniform(1.03, 1.18)  # an overrun to flag on the dashboard
            # Bell-shaped monthly weights (slow start, peak, taper) with noise.
            n = len(months)
            weights = [(0.3 + (i + 0.5) / n * (1 - (i + 0.5) / n)) * self.rng.uniform(0.6, 1.4) for i in range(n)]
            scale = float(po.amount) * share / sum(weights)
            for month, w in zip(months, weights):
                invoice_date = month + datetime.timedelta(days=self.rng.randint(0, 6))
                if invoice_date > self.today:
                    continue
                received = invoice_date + datetime.timedelta(days=self.rng.randint(1, 7))
                received = min(received, self.today)
                age = (self.today - received).days
                status, paid = IS.PAID, received + datetime.timedelta(days=self.rng.randint(14, 40))
                if paid > self.today:
                    status, paid = self.rng.choices(
                        [IS.RECEIVED, IS.UNDER_REVIEW, IS.APPROVED],
                        weights=[3, 4, 3] if age > 10 else [6, 3, 1],
                    )[0], None
                elif self.rng.random() < 0.015:
                    status, paid = IS.REJECTED, None
                invoices.append(Invoice(
                    invoice_number=self.invoice_number(po.vendor),
                    vendor=po.vendor,
                    purchase_order=po,
                    status=status,
                    amount=Decimal(scale * w).quantize(Decimal("0.01")),
                    invoice_date=invoice_date,
                    received_date=received,
                    paid_date=paid,
                ))
        for inv in invoices:
            inv.full_clean(validate_unique=False, validate_constraints=False)
        Invoice.objects.bulk_create(invoices, batch_size=500)
        self.backdate(Invoice, invoices, [inv.received_date for inv in invoices])
        return invoices

    # -- field reports ---------------------------------------------------------
    def make_field_reports(self, plans):
        reports = []
        for plan in plans:
            if plan.construction_start:
                start, end, count = plan.construction_start, min(plan.construction_end, self.today), self.rng.randint(10, 28)
            elif plan.category in ("study", "development", "environmental") and plan.project.status in (
                Project.Status.DESIGN, Project.Status.COMPLETE, Project.Status.CONSTRUCTION
            ):
                start, end, count = plan.start, min(add_months(plan.start, 14), self.today), self.rng.randint(2, 8)
            else:
                continue
            dates = sorted({self.date_between(start, end) for _ in range(count)})
            observations = OBSERVATIONS[plan.category]
            for d in dates:
                reports.append(FieldReport(
                    project=plan.project,
                    entered_by=plan.project.project_manager if self.rng.random() < 0.2 else self.pick(INSPECTORS),
                    report_date=d,
                    data_entry_date=min(d + datetime.timedelta(days=self.rng.choice([0, 0, 0, 1, 1, 2, 3])), self.today),
                    time_on_site=Decimal(self.rng.randint(2, 32)) / 4,
                    observation_notes=" ".join(self.fill(t) for t in self.rng.sample(observations, 2)),
                    safety_notes=self.pick(SAFETY),
                    weather_notes=self.pick(WEATHER[SEASON[d.month]]),
                ))
        for r in reports:
            r.full_clean()
        FieldReport.objects.bulk_create(reports, batch_size=500)
        self.backdate(FieldReport, reports, [r.data_entry_date for r in reports])
        return reports

    # -- documents -------------------------------------------------------------
    def make_documents(self, plans):
        DT = Document.DocumentType
        docs, stamps = [], []
        for plan in plans:
            in_construction = plan.construction_start is not None
            types = [DT.LETTER, DT.MEMO, DT.EMAIL, DT.MEETING_MINUTES, DT.REPORT]
            if in_construction:
                types += [DT.RFI, DT.RFI, DT.SUBMITTAL, DT.SUBMITTAL, DT.CHANGE_ORDER, DT.DRAWING]
            elif plan.project.status != Project.Status.PLANNING:
                types += [DT.DRAWING]
            end = min(plan.construction_end or add_months(plan.start, 18), self.today)
            counters = {}
            for _ in range(self.rng.randint(3, 12) if plan.project.status != Project.Status.PLANNING else self.rng.randint(1, 3)):
                doc_type = self.pick(types)
                counters[doc_type] = counters.get(doc_type, 0) + 1
                subject = self.pick(DOC_SUBJECTS[doc_type])
                if doc_type == DT.RFI:
                    subject = f"RFI #{counters[doc_type]:03d} — {subject}"
                elif doc_type == DT.SUBMITTAL:
                    subject = f"Submittal {counters[doc_type]:02d}: {subject}"
                elif doc_type == DT.CHANGE_ORDER:
                    subject = f"Change Order No. {counters[doc_type]} — {subject}"
                elif doc_type == DT.MEETING_MINUTES and subject == "Progress Meeting":
                    subject = f"Progress Meeting No. {counters[doc_type]} Minutes"
                elif doc_type == DT.MEETING_MINUTES:
                    subject = f"{subject} Minutes"

                # Who sent it to whom.
                counterpart = (plan.contractor if in_construction and doc_type in (DT.RFI, DT.SUBMITTAL, DT.CHANGE_ORDER)
                               else plan.design_vendor)
                counterpart_name = counterpart.name if counterpart else f"{self.pick(SUBDIVISIONS)} Development LLC"
                if doc_type in (DT.RFI, DT.SUBMITTAL, DT.REPORT, DT.DRAWING):
                    origin, recipient = counterpart_name, UTILITY
                elif doc_type == DT.LETTER and self.rng.random() < 0.3:
                    origin, recipient = UTILITY, self.pick(AGENCIES)
                else:
                    origin, recipient = UTILITY, counterpart_name
                if doc_type == DT.EMAIL and self.rng.random() < 0.4:
                    origin, recipient = recipient, origin

                doc_date = self.date_between(plan.start, end)
                docs.append(Document(
                    project=plan.project, subject=subject, originating_organization=origin,
                    recipient_organization=recipient, document_type=doc_type, document_date=doc_date,
                ))
                added = doc_date + datetime.timedelta(days=self.rng.randint(0, 5))
                edited = added + datetime.timedelta(days=self.rng.choice([0, 0, 0, 1, 4, 12]))
                stamps.append((min(added, self.today), min(edited, self.today)))
        for d in docs:
            d.full_clean()
        Document.objects.bulk_create(docs, batch_size=500)
        # added/last-edited are auto timestamps; backdate them so the demo looks lived-in.
        for doc, (added, edited) in zip(docs, stamps):
            doc.added_date = doc.created_at = self.aware(added)
            doc.last_edited_date = doc.updated_at = self.aware(edited)
        Document.objects.bulk_update(docs, ["added_date", "last_edited_date", "created_at", "updated_at"], batch_size=500)
        return docs

    def backdate(self, model, objs, created_dates, extra_fields=()):
        """Overwrite auto timestamps so records look like they were entered over time."""
        for obj, d in zip(objs, created_dates):
            obj.created_at = obj.updated_at = self.aware(min(d, self.today))
        model.objects.bulk_update(objs, ["created_at", "updated_at", *extra_fields], batch_size=500)

    def aware(self, d):
        """A timezone-aware working-hours timestamp on date ``d``."""
        moment = datetime.datetime.combine(d, datetime.time(8)) + datetime.timedelta(minutes=self.rng.randint(0, 540))
        return min(timezone.make_aware(moment), timezone.now())

    # -- entry point -----------------------------------------------------------
    def run(self):
        vendors = self.make_vendors()
        plans = self.make_projects()
        pos = self.make_purchase_orders(plans)
        invoices = self.make_invoices(pos)
        reports = self.make_field_reports(plans)
        documents = self.make_documents(plans)
        counts = {
            "vendors": len(vendors), "projects": len(plans), "purchase orders": len(pos),
            "invoices": len(invoices), "field reports": len(reports), "documents": len(documents),
        }
        for extension in EXTENSIONS:
            counts.update(extension(self, plans))
        return counts


def generate(seed=42, today=None, project_count=100):
    """Create the demo dataset. Assumes the pm tables are empty."""
    return Generator(seed=seed, today=today, project_count=project_count).run()
