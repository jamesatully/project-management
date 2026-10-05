"""
Fictitious planning data for the demo utility: plans, objectives, risks,
stakeholders, milestones, communication plans and monthly activity notes.

Runs as an extension of ``pm.demo`` (registered at import, from
PlanningConfig.ready()), so ``manage.py seed_demo`` creates everything. Uses
its own random stream so adding planning data doesn't change the pm dataset.
"""
import datetime
import random
import re

from django.utils import timezone

from pm import demo as pm_demo
from pm.demo import FIRST, LAST, UTILITY, add_months
from pm.models import Project

from .models import ActivityNote, CommunicationItem, Milestone, Objective, ProjectPlan, Risk, Stakeholder

S = Project.Status
ENGINEERING_MANAGER = "Renee Castellano"  # fictitious approver of plans

# --- Plan narrative -------------------------------------------------------------

PROBLEMS = {
    "water_main": (
        "The existing {d}-inch cast iron water main serving this corridor was installed in the {decade}s and has "
        "experienced {k} breaks in the last five years. Each break interrupts service to customers, adds to water "
        "loss and requires costly emergency repairs. Hydraulic modeling also shows the corridor cannot deliver "
        "required fire flows. Replacing the main now, before failures accelerate, is the lowest life-cycle-cost option."
    ),
    "sewer": (
        "CCTV inspection of sewers in the project area found structural defects — cracks, root intrusion and offset "
        "joints — rated PACP grade 4 or 5 in about {pct}% of the pipe. Inflow and infiltration during wet weather "
        "contributes to capacity problems downstream and increases treatment costs. Without rehabilitation, the risk "
        "of pipe collapses and sanitary sewer overflows will continue to grow."
    ),
    "plant": (
        "Equipment at {facility} is at or beyond the end of its useful life. Recent failures have required emergency "
        "repairs, and replacement parts are increasingly difficult to obtain. Continued deterioration puts permit "
        "compliance and reliable service at risk, while newer technology offers significant energy savings."
    ),
    "storage": (
        "A recent condition inspection identified coating failure, corrosion and outdated equipment, as well as "
        "deficiencies against current seismic and sanitary standards. The facility is critical to maintaining "
        "pressure, fire-flow storage and supply reliability in its service zone."
    ),
    "study": (
        "The utility's current planning information in this area is more than {k} years old and no longer reflects "
        "growth projections, regulatory requirements or asset condition data. An updated study is needed to guide "
        "capital investment and to support rate-setting and state and federal funding applications."
    ),
    "environmental": (
        "Utility facilities and past operations have affected stream and riparian habitat in the project area. "
        "Regulatory permits require the utility to restore the affected area, monitor results and demonstrate "
        "improved water quality and habitat function over the monitoring period."
    ),
    "development": (
        "New development requires extension of public water and sewer mains to serve new lots. The developer will "
        "design and build the facilities to utility standards; the utility must review plans, inspect construction "
        "and accept the new assets into its system."
    ),
}

SCOPE = {
    "water_main": (
        "- Replace approximately {lf} LF of cast iron main with {d2}-inch ductile iron pipe\n"
        "- Reconnect about {svc} water services and replace meter boxes\n"
        "- Replace fire hydrants and gate valves within the project limits\n"
        "- Trench and pavement restoration\n- Temporary water service during construction",
        "- Private-side service line replacement\n- Sewer or storm drain improvements\n"
        "- Street reconstruction beyond the trench restoration limits\n- Sidewalk and streetlight improvements (by City)",
    ),
    "sewer": (
        "- Rehabilitate approximately {lf} LF of 8- to 24-inch sewer by cured-in-place pipe (CIPP) lining\n"
        "- Reinstate and seal service lateral connections\n- Rehabilitate {k} manholes\n"
        "- Bypass pumping and traffic control\n- Pre- and post-construction CCTV inspection",
        "- Private side sewers beyond the property-line cleanout\n- Capacity upsizing (addressed by the Sewer Master Plan)\n"
        "- Storm drainage improvements",
    ),
    "plant": (
        "- Replace process equipment with associated piping, valves and supports\n"
        "- Electrical, instrumentation and SCADA integration\n"
        "- Temporary facilities to keep the plant in service during construction\n"
        "- Startup, testing, O&M manuals and operator training",
        "- Treatment capacity expansion\n- Unrelated building or site improvements\n- Changes to permit limits",
    ),
    "storage": (
        "- Surface preparation and recoating, or equipment replacement, as identified in the condition assessment\n"
        "- Seismic and sanitary upgrades (vents, hatches, overflow)\n- Temporary operations plan for the service zone\n"
        "- Disinfection, testing and return to service",
        "- Increasing storage or pumping capacity\n- Distribution system improvements outside the site",
    ),
    "study": (
        "- Data collection and review of existing records, GIS and operating data\n"
        "- Analysis and evaluation of alternatives\n- Staff and stakeholder workshops\n"
        "- Draft and final report with a prioritized, costed list of recommendations",
        "- Design of recommended improvements\n- Environmental permitting\n- Implementation of rate changes",
    ),
    "environmental": (
        "- Site restoration: grading, large woody debris and native plantings\n- Erosion and sediment control\n"
        "- Water quality and vegetation monitoring\n- Annual monitoring reports to regulatory agencies",
        "- Work outside utility property or easements\n- Maintenance beyond the permit monitoring period",
    ),
    "development": (
        "- Plan review and approval\n- Construction inspection and testing\n"
        "- Acceptance of public mains, hydrants and appurtenances\n- Collection of system development charges",
        "- Design or construction of facilities (by the developer)\n- Private on-site plumbing\n"
        "- Off-site capacity improvements",
    ),
}

# --- Objectives: (description, success measure) ----------------------------------

BUDGET_OBJECTIVE = ("Deliver within the approved budget", "Final cost within 5% of the approved project budget")
OBJECTIVES = {
    "water_main": [
        ("Replace aging, break-prone water main", "No main breaks in the project limits for two years after completion"),
        ("Improve fire flow", "Hydrant flow tests meet 1,500 gpm at 20 psi residual"),
        ("Minimize customer service interruptions", "No planned outage longer than 6 hours; 48-hour notice for every shutdown"),
        ("Restore streets to City standards", "Final paving accepted by City Public Works"),
    ],
    "sewer": [
        ("Reduce inflow and infiltration", "Wet-weather flow in the basin reduced by at least 20%"),
        ("Eliminate sanitary sewer overflows at known locations", "Zero overflows during a 5-year storm"),
        ("Extend pipe service life", "Rehabilitated pipe rated for a 50-year design life"),
        ("Maintain sewer service during construction", "No backups attributable to bypass pumping"),
    ],
    "plant": [
        ("Maintain permit compliance throughout construction", "No permit exceedances attributable to construction"),
        ("Replace equipment at end of service life", "New equipment commissioned and accepted by Operations"),
        ("Reduce energy use", "Process energy use reduced by 20% compared with baseline"),
        ("Prepare operators to run the new system", "All operators complete O&M training before final acceptance"),
    ],
    "storage": [
        ("Extend facility service life", "Coating system warranted for 20 years; condition rating improved to Good"),
        ("Meet current seismic and sanitary standards", "Upgrades verified by structural engineer and Health Department"),
        ("Maintain pressure and fire storage during the outage", "No pressure complaints in the zone during construction"),
    ],
    "study": [
        ("Produce a prioritized 10-year capital program", "Board adopts the recommended project list"),
        ("Build a reliable planning model", "Model calibrated within 5 psi or 10% flow at 90% of test points"),
        ("Engage staff and the public", "Two staff workshops and one public meeting held"),
        ("Identify funding strategies", "Funding plan, including grant and loan options, in the final report"),
    ],
    "environmental": [
        ("Restore riparian habitat", "80% plant survival at year 3"),
        ("Meet mitigation permit conditions", "Regulators accept each annual monitoring report"),
        ("Improve water quality", "Temperature and turbidity targets met at downstream station"),
        ("Coordinate with resource agencies", "All in-water work completed within approved work windows"),
    ],
    "development": [
        ("Ensure new infrastructure meets utility standards", "Mains pass pressure, bacteriological and mandrel tests"),
        ("Provide timely plan review", "Each review cycle completed within 30 days"),
        ("Accept assets into utility records", "Record drawings received and GIS updated within 60 days"),
    ],
}

# --- Risks: (title, category, description, mitigation, likelihood range, impact range, design-phase only) ----

GENERAL_RISKS = [
    ("Construction cost escalation", "COST", "Bid prices may exceed the engineer's estimate due to market conditions.",
     "Carry 15% contingency; use bid alternates; update the estimate at each design milestone.", (2, 4), (3, 5), True),
    ("Funding timing", "COST", "State revolving fund loan approval may not align with the planned bid date.",
     "Coordinate early with the funding agency; keep a bridge-funding option with Finance.", (1, 3), (3, 4), True),
    ("Long lead times for electrical equipment", "PROCUREMENT",
     "Switchgear, motor control centers and generators currently have 40–60 week lead times.",
     "Pre-purchase long-lead items; allow approved-equal substitutions.", (3, 5), (3, 4), False),
    ("Limited contractor interest", "PROCUREMENT", "Few qualified bidders may respond in a busy construction season.",
     "Advertise early in the year; hold a pre-bid outreach meeting.", (2, 3), (2, 4), True),
    ("Permitting delays", "REGULATORY", "Required permits may take longer than the schedule assumes.",
     "Hold pre-application meetings early; track permit status in the monthly update.", (2, 4), (2, 4), True),
    ("Worker safety incident", "SAFETY", "Trenching, confined space and traffic exposures on site.",
     "Site-specific safety plan; daily tailgate meetings; inspector oversight.", (1, 2), (4, 5), False),
]
CATEGORY_RISKS = {
    "water_main": [
        ("Unknown or mislocated utilities", "TECHNICAL", "Gas, telecom and storm lines may not match record drawings.",
         "Pothole critical crossings during design; require locates before excavation.", (3, 4), (2, 4), False),
        ("Customer complaints about outages", "STAKEHOLDER", "Planned shutdowns affect homes and businesses.",
         "48-hour door hangers; schedule shutdowns at night for businesses.", (3, 4), (2, 3), False),
        ("Traffic impacts on an arterial street", "STAKEHOLDER", "Lane closures may cause congestion and complaints.",
         "Approved traffic control plan; restrict work hours on peak days.", (3, 4), (2, 3), False),
        ("Rock excavation", "COST", "Shallow bedrock could require hammering or blasting.",
         "Geotechnical borings during design; unit-price bid item for rock.", (2, 3), (3, 4), False),
    ],
    "sewer": [
        ("Bypass pumping failure", "ENVIRONMENTAL", "Pump failure during bypass could cause a sewage spill.",
         "Redundant pumps, 24/7 monitoring and an approved spill response plan.", (1, 2), (4, 5), False),
        ("Pipe condition worse than CCTV indicated", "TECHNICAL", "Collapsed sections may not be linable.",
         "Pre-lining CCTV; unit-price item for point repairs.", (2, 4), (3, 4), False),
        ("Odor complaints during CIPP curing", "STAKEHOLDER", "Styrene odors may concern nearby residents.",
         "Advance notice; ventilation at manholes; consider UV-cured liner.", (3, 4), (1, 3), False),
        ("Lateral reinstatement problems", "TECHNICAL", "Missed or partially reopened laterals cause backups.",
         "Pre- and post-CCTV of all laterals; contractor on call during reinstatement.", (2, 3), (3, 4), False),
    ],
    "plant": [
        ("Permit compliance during process shutdowns", "OPERATIONS", "Taking units offline reduces treatment redundancy.",
         "Detailed shutdown sequencing plan approved by Operations; schedule outside wet season.", (2, 3), (4, 5), False),
        ("SCADA integration issues", "TECHNICAL", "New equipment may not integrate cleanly with legacy controls.",
         "Early integration workshop; factory acceptance testing.", (3, 4), (2, 4), False),
        ("Hazardous building materials", "ENVIRONMENTAL", "Lead paint or asbestos may be present in existing structures.",
         "Hazardous materials survey during design; abatement bid item.", (2, 3), (2, 3), True),
        ("Operator availability for startup", "OPERATIONS", "Staff vacancies may limit startup and training support.",
         "Schedule training early; include extended manufacturer support.", (2, 4), (2, 3), False),
    ],
    "storage": [
        ("Water quality during facility outage", "OPERATIONS", "Taking storage offline may affect chlorine residual and pressure.",
         "Temporary operations plan; increased sampling in the zone.", (2, 3), (3, 4), False),
        ("Weather delays to coating work", "SCHEDULE", "Coating requires dry, mild conditions to cure.",
         "Schedule coating in summer; allow dehumidification equipment.", (3, 4), (2, 3), False),
        ("Changing regulatory limits", "REGULATORY", "New drinking water limits could change treatment requirements.",
         "Design for flexibility; track rulemaking monthly.", (2, 3), (3, 5), True),
    ],
    "study": [
        ("Data gaps", "TECHNICAL", "Asset and flow data may be incomplete or inconsistent.",
         "Early data inventory; targeted field verification.", (3, 4), (2, 3), False),
        ("Stakeholder disagreement on priorities", "STAKEHOLDER", "Departments may rank needs differently.",
         "Agree on scoring criteria before ranking projects.", (2, 3), (2, 3), False),
        ("Scope creep", "SCHEDULE", "Additional questions may expand the study beyond its budget.",
         "Change management process; park new items for future phases.", (3, 4), (2, 3), False),
    ],
    "environmental": [
        ("Plant mortality from drought", "ENVIRONMENTAL", "Hot, dry summers can reduce planting survival.",
         "Temporary irrigation for two seasons; replant as needed.", (3, 4), (2, 3), False),
        ("In-water work window", "REGULATORY", "In-water work is limited to a short summer window.",
         "Schedule critical-path in-water work first; pre-order materials.", (3, 4), (3, 4), False),
        ("Invasive species", "ENVIRONMENTAL", "Blackberry and knotweed may out-compete new plantings.",
         "Pre-treatment and maintenance weeding during monitoring.", (3, 5), (2, 3), False),
        ("Cultural resources discovery", "REGULATORY", "Excavation could uncover archaeological resources.",
         "Inadvertent discovery plan; archaeological monitoring during excavation.", (1, 2), (3, 4), False),
    ],
    "development": [
        ("Developer schedule changes", "SCHEDULE", "Development phasing may shift with market conditions.",
         "Monthly coordination with the developer.", (3, 4), (1, 2), False),
        ("Substandard installation", "TECHNICAL", "Contractor work may not meet utility standards.",
         "Full-time inspection during main installation; testing before acceptance.", (2, 3), (2, 4), False),
        ("Incomplete record drawings", "TECHNICAL", "As-builts may be late or inaccurate.",
         "Hold final acceptance until record drawings are approved.", (3, 4), (1, 2), False),
    ],
}

# --- Milestones: (name, phase, months from start; None = anchored to construction dates) ----
# Phase rank: 0 = initiation, 1 = design/study, 2 = construction, 3 = closeout.

MILESTONES = {
    "capital": [
        ("Project charter approved", 0, 0.5), ("30% design submittal", 1, 3), ("60% design submittal", 1, 6),
        ("90% design submittal", 1, 9), ("Permits obtained", 1, 10), ("Bid advertisement", 1, "cs-3"),
        ("Contract award / Notice to Proceed", 2, "cs"), ("Substantial completion", 2, "ce"),
        ("Final acceptance and closeout", 3, "ce+2"),
    ],
    "study": [
        ("Kickoff meeting", 0, 0.5), ("Data collection complete", 1, 4), ("Alternatives workshop", 1, 6),
        ("Draft report", 1, 8), ("Final report", 1, 10), ("Presentation to Board", 3, 11),
    ],
    "environmental": [
        ("Project charter approved", 0, 0.5), ("Permit applications submitted", 1, 3), ("Permits issued", 1, 7),
        ("Restoration construction start", 2, "cs"), ("Planting complete", 2, "ce"),
        ("Year 1 monitoring report", 3, "ce+12"), ("Year 3 monitoring report", 3, "ce+36"),
    ],
    "development": [
        ("Plan review complete", 1, 2), ("Pre-construction meeting", 2, 4), ("Mains tested and accepted", 2, 9),
        ("Final acceptance and record drawings", 3, 12),
    ],
}
MAX_PHASE = {S.PLANNING: 0, S.DESIGN: 1, S.ON_HOLD: 1, S.CANCELLED: 1, S.CONSTRUCTION: 2, S.COMPLETE: 3}

# --- Stakeholders: (name or None for a generated person, organization, role, influence, interest) ----

STAKEHOLDERS_COMMON = [
    (ENGINEERING_MANAGER, UTILITY, "Engineering Division Manager — project sponsor", "HIGH", "HIGH"),
    ("Board of Commissioners", UTILITY, "Approves budget and contract award", "HIGH", "MEDIUM"),
    (None, f"{UTILITY} — Finance", "Budget analyst", "MEDIUM", "MEDIUM"),
]
STAKEHOLDERS = {
    "water_main": [
        (None, f"{UTILITY} — Water Distribution", "Distribution superintendent", "MEDIUM", "HIGH"),
        (None, f"{UTILITY} — Customer Service", "Customer service manager", "LOW", "HIGH"),
        ("{area} Neighborhood Association", "Community group", "Residents along the work zone", "LOW", "HIGH"),
        (None, "Riverbend Fire Department", "Fire marshal (hydrant outages)", "MEDIUM", "MEDIUM"),
        (None, "City of Riverbend Public Works", "Right-of-way and paving permits", "HIGH", "LOW"),
    ],
    "sewer": [
        (None, f"{UTILITY} — Collection System", "Collections superintendent", "MEDIUM", "HIGH"),
        ("{area} Neighborhood Association", "Community group", "Residents along the work zone", "LOW", "HIGH"),
        (None, "State Department of Environmental Quality", "Wastewater permit coordinator", "HIGH", "MEDIUM"),
        (None, "City of Riverbend Public Works", "Right-of-way permits", "HIGH", "LOW"),
    ],
    "plant": [
        (None, f"{UTILITY} — Treatment Operations", "Plant superintendent", "HIGH", "HIGH"),
        (None, f"{UTILITY} — Maintenance", "Maintenance supervisor", "MEDIUM", "HIGH"),
        (None, "State Department of Environmental Quality", "Permit writer", "HIGH", "MEDIUM"),
        (None, f"{UTILITY} — SCADA", "Controls engineer", "MEDIUM", "HIGH"),
    ],
    "storage": [
        (None, f"{UTILITY} — Water Operations", "Water operations supervisor", "MEDIUM", "HIGH"),
        (None, "County Health Department — Drinking Water Program", "Drinking water regulator", "HIGH", "MEDIUM"),
        ("{area} Neighborhood Association", "Community group", "Nearby residents", "LOW", "MEDIUM"),
    ],
    "study": [
        (None, f"{UTILITY} — Operations", "Operations manager", "MEDIUM", "HIGH"),
        (None, f"{UTILITY} — Asset Management", "Asset management lead", "MEDIUM", "HIGH"),
        ("Ratepayer Advisory Committee", "Community group", "Reviews rate and capital impacts", "MEDIUM", "MEDIUM"),
    ],
    "environmental": [
        (None, "State Department of Environmental Quality", "Water quality specialist", "HIGH", "HIGH"),
        (None, "State Fish and Wildlife Agency", "Habitat biologist", "HIGH", "MEDIUM"),
        ("{creek} Watershed Council", "Community group", "Local restoration partner", "LOW", "HIGH"),
    ],
    "development": [
        ("{subdivision} Development LLC", "Developer", "Applicant; designs and builds the facilities", "MEDIUM", "HIGH"),
        (None, f"{UTILITY} — Development Services", "Plan reviewer", "MEDIUM", "HIGH"),
        (None, "City of Riverbend Planning Department", "Land-use approvals", "HIGH", "LOW"),
    ],
}

# --- Communication plan: (purpose, audience, method, frequency, owner key) ----------

COMMS_COMMON = [
    ("Monthly project status report", "Engineering Division Manager", "REPORT", "MONTHLY", "pm"),
    ("Budget and schedule update", "Board of Commissioners", "PRESENTATION", "QUARTERLY", "sponsor"),
]
COMMS = {
    "construction": [
        ("Weekly construction progress meeting", "Contractor, inspector and design engineer", "MEETING", "WEEKLY", "pm"),
        ("Construction notices", "Residents and businesses in the work area", "PUBLIC_NOTICE", "MILESTONE", "pio"),
        ("Project web page updates", "General public", "WEBSITE", "MONTHLY", "pio"),
        ("Shutdown coordination", "Operations staff", "MEETING", "AS_NEEDED", "pm"),
    ],
    "study": [
        ("Technical workshops", "Utility engineering and operations staff", "MEETING", "MILESTONE", "pm"),
        ("Public meeting", "Customers and community groups", "PRESENTATION", "MILESTONE", "pio"),
        ("Draft report review", "Engineering Division Manager", "REPORT", "MILESTONE", "pm"),
    ],
    "environmental": [
        ("Regulatory coordination", "State Department of Environmental Quality", "EMAIL", "AS_NEEDED", "pm"),
        ("Annual monitoring report", "Resource agencies", "REPORT", "QUARTERLY", "pm"),
        ("Volunteer planting days", "Watershed council and community", "NEWSLETTER", "MILESTONE", "pio"),
    ],
    "development": [
        ("Plan review comments", "Developer and their engineer", "EMAIL", "AS_NEEDED", "pm"),
        ("Inspection scheduling", "Developer's contractor", "EMAIL", "WEEKLY", "inspector"),
    ],
}
PIO = "Nadia Brooks"  # fictitious public information officer

# --- Activity note text ------------------------------------------------------------

DESIGN_ACTIVITY = [
    "The design consultant submitted the {pct}% design package and staff returned review comments",
    "Topographic survey and potholing of existing utilities were completed",
    "Geotechnical borings were completed at {k} locations; the draft geotechnical report is under review",
    "We coordinated the alignment with City Public Works to avoid a newly paved segment",
    "We held a design review workshop with Operations staff to confirm equipment preferences",
    "Permit applications were submitted to the State Department of Environmental Quality",
    "The engineer's estimate was updated to reflect current bid prices",
    "Bid documents and specifications were finalized for legal review",
]
CONSTRUCTION_ACTIVITY = {
    "water_main": ["The contractor installed about {lf} LF of new main and completed {k} service reconnections",
                   "Pressure testing and disinfection of the completed segment passed",
                   "Two planned shutdowns were completed with advance notice to customers"],
    "sewer": ["The contractor lined about {lf} LF of sewer and reinstated {k} laterals",
              "Bypass pumping operated without incident",
              "{k} manholes were rehabilitated"],
    "plant": ["The contractor set new equipment and completed electrical rough-in",
              "Concrete work for the new structures progressed on schedule",
              "Startup testing began with the manufacturer's representative on site"],
    "storage": ["Surface preparation and coating progressed to about {pct}% complete",
                "Pump installation and alignment were completed",
                "Disinfection and water quality sampling were completed"],
    "environmental": ["Grading and placement of large woody debris were completed",
                      "Crews and volunteers planted about {lf} native trees and shrubs",
                      "Erosion control measures were inspected after heavy rain and repaired"],
    "development": ["We inspected main installation and witnessed pressure testing",
                    "Bacteriological samples passed and the new mains were approved for service",
                    "A punch list of {k} items was issued to the developer"],
}
STUDY_ACTIVITY = [
    "The consultant completed data collection and the asset condition summary",
    "Flow monitoring continued at {k} locations",
    "We held a staff workshop to review alternatives and evaluation criteria",
    "The draft report was received and distributed for staff review",
    "Model calibration was completed against hydrant flow tests",
]
ISSUES = [
    "One RFI about an unexpected utility conflict was resolved without cost impact.",
    "A change order for additional rock excavation is under review.",
    "No safety incidents were reported.",
    "Two customer complaints about traffic were addressed with revised detour signage.",
    "Equipment delivery slipped three weeks; the contractor resequenced work to compensate.",
    "No issues requiring escalation this month.",
]
SPENDING = [
    "Spending remains within budget.",
    "Spending is tracking slightly above plan; contingency remains adequate.",
    "Costs to date are in line with the schedule of values.",
]
DECISIONS = [
    ("Approved CIPP lining for Reach 3 instead of open-cut replacement", "Saves an estimated four weeks and reduces traffic impacts."),
    ("Deferred final paving to spring", "Avoids placing asphalt in cold, wet conditions; temporary patching will be maintained."),
    ("Selected Alternative B as the preferred alternative", "Lowest life-cycle cost and preferred by Operations staff."),
    ("Authorized pre-purchase of long-lead electrical equipment", "Protects the construction schedule given 50-week lead times."),
    ("Approved a 60-day time extension", "Extension reflects weather delays and a permit condition outside the contractor's control."),
]
NOTE_ISSUES = [
    ("Unexpected rock encountered", "Rock was encountered between stations 12+00 and 14+50. Unit-price quantities are being tracked."),
    ("Equipment delivery delayed", "The supplier reports an eight-week delay on a key equipment item. Evaluating schedule impacts."),
    ("Permit condition requires additional monitoring", "The permit adds turbidity monitoring during in-water work; budget impact is minor."),
    ("Conflict with an unmapped utility", "An unmapped telecom duct conflicts with the alignment; redesign of a short segment is under way."),
]


class PlanningGenerator:
    def __init__(self, generator):
        self.gen = generator
        self.today = generator.today
        self.rng = random.Random(generator.seed * 7919 + 17)
        self._schedules = {}

    def pick(self, seq):
        return self.rng.choice(seq)

    def person(self):
        return f"{self.pick(FIRST)} {self.pick(LAST)}"

    def fmt(self, text, plan):
        r = self.rng
        name = plan.project.name
        return text.format(
            d=r.choice([6, 8, 10, 12]), d2=r.choice([8, 12, 16]), decade=r.choice([1940, 1950, 1960]),
            k=r.randint(3, 14), pct=r.choice([30, 60, 90]) if "design" in text else r.randint(20, 45),
            lf=r.randrange(400, 6000, 50), svc=r.randint(20, 160),
            facility=(re.match(r"^(.*?(?:WWTP|WRF|WTP))", name) or [None, "the treatment plant"])[1],
            area=self.pick(pm_demo.AREAS), creek=self.pick(pm_demo.CREEKS),
            subdivision=name.split(" ")[0] if plan.category == "development" else self.pick(pm_demo.SUBDIVISIONS),
        )

    def schedule(self, plan):
        """Construction start/end, estimated (once per project) when pm created no construction POs."""
        if id(plan) not in self._schedules:
            cs = plan.construction_start or add_months(plan.start, self.rng.randint(13, 20))
            ce = plan.construction_end or add_months(cs, self.rng.randint(8, 18))
            self._schedules[id(plan)] = (cs, ce)
        return self._schedules[id(plan)]

    # -- plan -------------------------------------------------------------------
    def plan(self, plan):
        status = plan.project.status
        if status == S.PLANNING and self.rng.random() < 0.3:
            return None
        plan_status = ProjectPlan.Status.APPROVED
        if status == S.PLANNING:
            plan_status = ProjectPlan.Status.DRAFT
        elif status == S.DESIGN and self.rng.random() < 0.3:
            plan_status = ProjectPlan.Status.IN_REVIEW
        approved = plan_status == ProjectPlan.Status.APPROVED
        scope_in, scope_out = SCOPE[plan.category]
        return ProjectPlan(
            project=plan.project,
            status=plan_status,
            problem_statement=self.fmt(PROBLEMS[plan.category], plan),
            scope_in=self.fmt(scope_in, plan),
            scope_out="" if plan_status == ProjectPlan.Status.DRAFT and self.rng.random() < 0.5 else scope_out,
            approved_by=ENGINEERING_MANAGER if approved else "",
            approved_date=min(plan.start + datetime.timedelta(days=self.rng.randint(25, 70)), self.today) if approved else None,
        )

    def objectives(self, plan, target):
        status = plan.project.status
        pool = OBJECTIVES[plan.category]
        chosen = self.rng.sample(pool, min(len(pool), self.rng.randint(2, 4))) + [BUDGET_OBJECTIVE]
        objs = []
        for i, (description, measure) in enumerate(chosen):
            if status == S.COMPLETE:
                obj_status = "ACHIEVED" if self.rng.random() < 0.85 else "NOT_ACHIEVED"
            elif status == S.CANCELLED:
                obj_status = "NOT_ACHIEVED"
            elif status == S.PLANNING:
                obj_status = "NOT_STARTED"
            elif status == S.ON_HOLD:
                obj_status = "AT_RISK"
            else:
                obj_status = "AT_RISK" if self.rng.random() < 0.15 else "ON_TRACK"
            objs.append(Objective(project=plan.project, description=description, success_measure=measure,
                                  target_date=target, status=obj_status, order=i + 1))
        return objs

    def risks(self, plan, owners):
        status = plan.project.status
        chosen = self.rng.sample(GENERAL_RISKS, self.rng.randint(2, 3))
        pool = CATEGORY_RISKS[plan.category]
        chosen += self.rng.sample(pool, min(len(pool), self.rng.randint(2, 4)))
        risks = []
        for title, category, description, mitigation, l_range, i_range, design_only in chosen:
            if status in (S.COMPLETE, S.CANCELLED) or (design_only and status == S.CONSTRUCTION):
                risk_status = Risk.Status.CLOSED
            else:
                risk_status = self.rng.choice([Risk.Status.OPEN, Risk.Status.OPEN, Risk.Status.MITIGATING])
            identified = min(plan.start + datetime.timedelta(days=self.rng.randint(5, 90)), self.today)
            review = None
            if risk_status != Risk.Status.CLOSED:
                # Mostly upcoming reviews, some overdue.
                review = self.today + datetime.timedelta(days=self.rng.randint(-40, 75))
            risks.append(Risk(
                project=plan.project, title=title, category=category, description=description,
                likelihood=self.rng.randint(*l_range), impact=self.rng.randint(*i_range), owner=self.pick(owners),
                mitigation=mitigation, status=risk_status, identified_date=identified, review_date=review,
            ))
        return risks

    def stakeholders(self, plan):
        rows = STAKEHOLDERS_COMMON + STAKEHOLDERS[plan.category]
        people = []
        for name, organization, role, influence, interest in rows:
            people.append(Stakeholder(
                project=plan.project, name=self.fmt(name, plan) if name else self.person(),
                organization=organization, role=role, influence=influence, interest=interest,
                contact=f"(503) 555-{self.rng.randint(150, 199):04d}" if name is None else "",
            ))
        if plan.design_vendor:
            people.append(Stakeholder(project=plan.project, name=plan.design_vendor.primary_contact_name,
                                      organization=plan.design_vendor.name, role="Consultant project manager",
                                      influence="MEDIUM", interest="HIGH"))
        if plan.contractor:
            people.append(Stakeholder(project=plan.project, name=self.person(), organization=plan.contractor.name,
                                      role="Contractor superintendent", influence="MEDIUM", interest="HIGH"))
        return people

    def milestones(self, plan):
        status = plan.project.status
        key = plan.category if plan.category in ("study", "environmental", "development") else "capital"
        cs, ce = self.schedule(plan)
        anchors = {"cs": cs, "cs-3": add_months(cs, -3), "ce": ce, "ce+2": add_months(ce, 2),
                   "ce+12": add_months(ce, 12), "ce+36": add_months(ce, 36)}
        rows = [(name, phase, anchors[offset] if isinstance(offset, str)
                 else plan.start + datetime.timedelta(days=int(offset * 30.4)))
                for name, phase, offset in MILESTONES[key]]
        # Projects that ran long were re-baselined: stretch the schedule so the first milestone
        # beyond the project's current phase falls in the future rather than years overdue.
        ahead = [planned for _, phase, planned in rows if phase > MAX_PHASE[status]]
        if status not in (S.COMPLETE, S.CANCELLED) and ahead and ahead[0] < self.today:
            target = self.today + datetime.timedelta(days=self.rng.randint(20, 150))
            factor = (target - plan.start).days / max((ahead[0] - plan.start).days, 1)
            rows = [(n, ph, plan.start + datetime.timedelta(days=int((d - plan.start).days * factor))) for n, ph, d in rows]

        slip = self.rng.randint(-7, 10)
        # About one active project in five is slipping on its remaining milestones.
        trouble = self.rng.randint(50, 110) if status in (S.DESIGN, S.CONSTRUCTION) and self.rng.random() < 0.2 else 0
        out, first_open = [], True
        for name, phase, planned in rows:
            slip += self.rng.randint(-6, 10) + (self.rng.randint(60, 150) if status == S.ON_HOLD and phase >= 1 else 0)
            projected = planned + datetime.timedelta(days=slip)
            m = Milestone(project=plan.project, name=name, planned_date=planned)
            if phase <= MAX_PHASE[status] and projected <= self.today:
                m.actual_date, m.status = projected, Milestone.Status.COMPLETE
            elif status == S.CANCELLED:
                m.status = Milestone.Status.MISSED if planned < self.today else Milestone.Status.NOT_STARTED
            else:
                projected += datetime.timedelta(days=trouble)
                m.forecast_date = max(projected, self.today + datetime.timedelta(days=self.rng.randint(7, 30)))
                late = (m.forecast_date - planned).days
                if late > 45 or status == S.ON_HOLD:
                    m.status = Milestone.Status.AT_RISK
                elif first_open and status != S.PLANNING:
                    m.status = Milestone.Status.IN_PROGRESS
                else:
                    m.status = Milestone.Status.NOT_STARTED
                first_open = False
            out.append(m)
        return out

    def communications(self, plan):
        kind = {"study": "study", "environmental": "environmental", "development": "development"}.get(
            plan.category, "construction")
        owners = {"pm": plan.project.project_manager, "sponsor": ENGINEERING_MANAGER, "pio": PIO,
                  "inspector": self.pick(pm_demo.INSPECTORS)}
        return [
            CommunicationItem(project=plan.project, purpose=purpose, audience=audience, method=method,
                              frequency=frequency, owner=owners[owner])
            for purpose, audience, method, frequency, owner in COMMS_COMMON + COMMS[kind]
        ]

    # -- activity notes -----------------------------------------------------------
    def monthly_body(self, plan, month, cs):
        if plan.category == "study":
            activity = self.pick(STUDY_ACTIVITY)
            next_step = "continue analysis and prepare for the next workshop"
        elif plan.category == "development":
            activity = self.pick(CONSTRUCTION_ACTIVITY["development"] + [
                "We returned plan review comments to the developer's engineer"])
            next_step = "continue inspections and coordinate testing with the developer"
        elif plan.construction_start and month >= cs:
            activity = self.pick(CONSTRUCTION_ACTIVITY[plan.category])
            next_step = self.pick(["continue construction in the next work zone", "complete testing of the current segment",
                                   "begin restoration work", "hold the monthly progress meeting with the contractor"])
        else:
            activity = self.pick(DESIGN_ACTIVITY)
            next_step = self.pick(["address review comments", "advance to the next design submittal",
                                   "finalize permit applications", "prepare the bid package"])
        lines = [
            f"Activities: {self.fmt(activity, plan)}.",
            self.pick(ISSUES),
            self.pick(SPENDING),
            f"Next month: {next_step}.",
        ]
        return "\n\n".join(lines)

    def notes(self, plan):
        status = plan.project.status
        if status == S.PLANNING:
            return []
        cs, ce = self.schedule(plan)
        end = self.today
        if status == S.COMPLETE:
            end = min(add_months(ce, 2) if plan.construction_start or plan.category in ("study", "development")
                      else add_months(plan.start, 14), self.today)
        elif status == S.CANCELLED:
            end = min(add_months(plan.start, self.rng.randint(4, 12)), self.today)
        elif status == S.ON_HOLD:
            end = min(add_months(plan.start, self.rng.randint(6, 14)), self.today)
        months, m = [], add_months(plan.start.replace(day=1), 1)
        while m < end.replace(day=1):
            months.append(m)
            m = add_months(m, 1)
        months = months[-18:]  # keep the most recent year and a half
        # Some active projects are behind on last month's update (shown on the dashboard).
        skip_last = status in (S.DESIGN, S.CONSTRUCTION) and self.rng.random() < 0.15

        notes = []
        for i, month in enumerate(months):
            if self.rng.random() < 0.04 or (skip_last and i == len(months) - 1):
                continue
            note_date = add_months(month, 1) + datetime.timedelta(days=self.rng.choice([0, 1, 1, 2, 2, 3, 4, 6]))
            if note_date > self.today:
                continue
            notes.append(ActivityNote(
                project=plan.project, note_type=ActivityNote.NoteType.MONTHLY, period=month, note_date=note_date,
                author_name=plan.project.project_manager if self.rng.random() < 0.92 else self.pick(pm_demo.INSPECTORS),
                body=self.monthly_body(plan, month, cs),
            ))
        if months:
            for note_type, pool in [(ActivityNote.NoteType.DECISION, DECISIONS), (ActivityNote.NoteType.ISSUE, NOTE_ISSUES)]:
                for title, body in self.rng.sample(pool, self.rng.choice([0, 0, 1, 1, 2])):
                    notes.append(ActivityNote(
                        project=plan.project, note_type=note_type, author_name=plan.project.project_manager,
                        note_date=self.gen.date_between(months[0], min(end, self.today)), title=title, body=body,
                    ))
        return notes

    # -- entry point --------------------------------------------------------------
    def run(self, plans):
        created = {ProjectPlan: [], Objective: [], Risk: [], Stakeholder: [], Milestone: [], CommunicationItem: [],
                   ActivityNote: []}
        for plan in plans:
            project_plan = self.plan(plan)
            if project_plan is None:
                continue
            created[ProjectPlan].append(project_plan)
            milestones = self.milestones(plan)
            created[Milestone] += milestones
            created[Objective] += self.objectives(plan, milestones[-1].planned_date)
            stakeholders = self.stakeholders(plan)
            created[Stakeholder] += stakeholders
            owners = [plan.project.project_manager, plan.project.project_manager, ENGINEERING_MANAGER] + [
                s.name for s in stakeholders if s.organization.startswith(UTILITY) and s.name != "Board of Commissioners"]
            created[Risk] += self.risks(plan, owners)
            created[CommunicationItem] += self.communications(plan)
            created[ActivityNote] += self.notes(plan)

        for model, objs in created.items():
            for obj in objs:
                if isinstance(obj, Risk):
                    obj.score = obj.likelihood * obj.impact  # bulk_create skips save()
                obj.full_clean(validate_unique=False, validate_constraints=False)
            model.objects.bulk_create(objs, batch_size=500)

        # Backdate audit timestamps so plans and notes look like they were written over time.
        for plan_obj in created[ProjectPlan]:
            plan_obj.created_at = self.aware(plan_obj.approved_date or plan_obj.project.created_at.date())
            plan_obj.updated_at = max(plan_obj.created_at, self.aware(self.today - datetime.timedelta(days=self.rng.randint(1, 200))))
        ProjectPlan.objects.bulk_update(created[ProjectPlan], ["created_at", "updated_at"], batch_size=500)
        for note in created[ActivityNote]:
            note.created_at = note.updated_at = self.aware(note.note_date)
        ActivityNote.objects.bulk_update(created[ActivityNote], ["created_at", "updated_at"], batch_size=500)

        labels = {ProjectPlan: "project plans", Objective: "objectives", Risk: "risks", Stakeholder: "stakeholders",
                  Milestone: "milestones", CommunicationItem: "comm. plan items", ActivityNote: "activity notes"}
        return {labels[m]: len(objs) for m, objs in created.items()}

    def aware(self, d):
        moment = datetime.datetime.combine(d, datetime.time(8)) + datetime.timedelta(minutes=self.rng.randint(0, 540))
        return min(timezone.make_aware(moment), timezone.now())


def extend(generator, plans):
    return PlanningGenerator(generator).run(plans)


pm_demo.EXTENSIONS.append(extend)
