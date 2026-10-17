"""
Fictitious budget history for the demo utility.

Each project gets an initial budget when it starts, then an updated version in
each annual budget cycle while it's active: drafted in the fall, submitted in
spring and approved by the Board in September, which supersedes the previous
version. Early estimates run lower and earlier than later ones, as real ones do.
Versions for the cycle being prepared "today" are left as drafts or submissions.

Runs as an extension of ``pm.demo`` (registered at import, from
BudgetsConfig.ready()), with its own random stream so the pm and planning data
don't change.
"""

import datetime
import random
from decimal import Decimal

from django.utils import timezone

from pm import demo as pm_demo
from pm.demo import CATEGORIES, add_months
from pm.models import Project

from .models import Budget, BudgetAmount, BudgetLineItem, fiscal_year

S = Project.Status
B = Budget.Status
C = BudgetLineItem.Category
BOARD = "Board of Commissioners"

DESIGN_NOTES = [
    "Updated design cost to the negotiated consultant scope and fee.",
    "Estimate refined at 30% design; added allowance for utility conflicts.",
    "Construction estimate updated from the 60% design opinion of probable cost.",
    "Schedule adjusted to coordinate with the City's paving program.",
    "Escalated construction estimate to the midpoint of construction.",
    "Permitting took longer than planned; construction moved out one year.",
]
CONSTRUCTION_NOTES = [
    "Construction budget updated to the low bid plus contingency.",
    "Approved change orders added; remaining contingency carried forward.",
    "Cash flow re-spread to the contractor's baseline schedule.",
    "Remaining work re-estimated; unspent prior-year budget re-appropriated.",
]


def money(value):
    """Round to a plausible budget figure."""
    step = 1000 if value >= 100_000 else 100
    return Decimal(int(round(value / step)) * step).quantize(Decimal("0.01"))


class BudgetGenerator:
    def __init__(self, generator):
        self.gen = generator
        self.today = generator.today
        self.rng = random.Random(generator.seed * 104729 + 31)

    def spread(self, total, first, last, shape="even"):
        """``total`` over fiscal years ``first``..``last``: {fy: amount}."""
        years = list(range(first, last + 1))
        n = len(years)
        if shape == "front":
            weights = [n - i for i in range(n)]
        elif shape == "bell":
            weights = [(1 + min(i, n - 1 - i)) * self.rng.uniform(0.8, 1.2) for i in range(n)]
        else:
            weights = [1] * n
        amounts = {fy: money(total * w / sum(weights)) for fy, w in zip(years, weights)}
        return {fy: a for fy, a in amounts.items() if a}

    # -- current estimate -------------------------------------------------------
    def estimate(self, plan):
        """
        The latest estimate as ``[(category, description, total, first_fy, last_fy, shape, optional)]``,
        or None for projects the utility doesn't budget.
        """
        r = self.rng
        fy0 = fiscal_year(plan.start)
        if plan.category == "development":
            if r.random() < 0.5:
                return None  # developer-funded with no utility costs
            return [
                (
                    C.CAPITALIZED_OPERATING,
                    "Plan review and inspection staff time",
                    r.uniform(15_000, 60_000),
                    fy0,
                    fy0 + 1,
                    "even",
                    False,
                )
            ]

        spec = CATEGORIES[plan.category]
        const = None
        if spec["construction"]:
            const = float(plan.construction_po.amount) if plan.construction_po else r.uniform(*spec["construction"])
        design = (
            float(plan.design_po.amount)
            if plan.design_po
            else (const * r.uniform(0.08, 0.12) if const else r.uniform(60_000, 650_000))
        )
        cs = plan.construction_start or add_months(plan.start, r.randint(13, 22))
        ce = plan.construction_end or add_months(cs, r.randint(8, 30 if plan.category == "plant" else 18))
        design_end = add_months(cs, -1)

        if not const:
            return [
                (
                    C.DESIGN,
                    "Planning study",
                    design * 1.1,
                    fy0,
                    max(fy0, fiscal_year(add_months(plan.start, r.randint(10, 20)))),
                    "even",
                    False,
                ),
                (
                    C.CAPITALIZED_OPERATING,
                    "Utility staff time (capitalized)",
                    design * r.uniform(0.04, 0.08),
                    fy0,
                    fy0 + 1,
                    "even",
                    False,
                ),
            ]
        lines = [
            (
                C.DESIGN,
                "Engineering design" if plan.category != "environmental" else "Permitting and design",
                design * 1.1,
                fy0,
                max(fy0, fiscal_year(design_end)),
                "front",
                False,
            )
        ]
        if plan.category == "plant" and const > 8_000_000:
            lines.append(
                (C.CONSTRUCTION, "General contract", const * 0.85, fiscal_year(cs), fiscal_year(ce), "bell", False)
            )
            lines.append(
                (
                    C.CONSTRUCTION,
                    "Owner-furnished equipment",
                    const * 0.25,
                    fiscal_year(cs),
                    fiscal_year(cs),
                    "even",
                    True,
                )
            )
        else:
            lines.append(
                (
                    C.CONSTRUCTION,
                    "Construction contract and contingency",
                    const * 1.1,
                    fiscal_year(cs),
                    fiscal_year(ce),
                    "bell",
                    False,
                )
            )
        lines.append(
            (
                C.CONSTRUCTION,
                "Construction management and inspection",
                const * r.uniform(0.05, 0.09),
                fiscal_year(cs),
                fiscal_year(ce),
                "even",
                False,
            )
        )
        if plan.category in ("water_main", "sewer") and r.random() < 0.3:
            lines.append(
                (
                    C.LAND,
                    "Permanent and temporary easements",
                    r.uniform(15_000, 180_000),
                    max(fy0, fiscal_year(cs) - 1),
                    max(fy0, fiscal_year(cs) - 1),
                    "even",
                    True,
                )
            )
        elif plan.category in ("storage", "plant") and r.random() < 0.3:
            lines.append(
                (
                    C.LAND,
                    "Site acquisition",
                    r.uniform(200_000, 1_200_000),
                    max(fy0, fiscal_year(cs) - 1),
                    max(fy0, fiscal_year(cs) - 1),
                    "even",
                    True,
                )
            )
        elif plan.category == "environmental" and r.random() < 0.4:
            lines.append((C.LAND, "Conservation easement", r.uniform(40_000, 250_000), fy0, fy0, "even", True))
        lines.append(
            (
                C.CAPITALIZED_OPERATING,
                "Utility staff time (capitalized)",
                (design + const) * r.uniform(0.02, 0.04),
                fy0,
                fiscal_year(ce),
                "even",
                False,
            )
        )
        return lines

    # -- versions ----------------------------------------------------------------
    def cycles(self, plan, last_fy):
        """[(budget_year, created, submitted, approved, status)] for each version of the project's budget."""
        r, today, status = self.rng, self.today, plan.project.status
        fy0, next_cycle = fiscal_year(plan.start), fiscal_year(today) + 1
        if status == S.COMPLETE:
            last_cycle = min(max(last_fy, fy0), fiscal_year(today))
        elif status == S.CANCELLED:
            last_cycle = r.randint(fy0, fiscal_year(today))
        else:
            last_cycle = next_cycle

        created = min(plan.start + datetime.timedelta(days=r.randint(7, 30)), today)
        approved = created + datetime.timedelta(days=r.randint(20, 60))
        first = (
            (fy0, created, created, approved, B.APPROVED) if approved <= today else (fy0, created, None, None, B.DRAFT)
        )
        versions = [first]
        for cycle in range(fy0 + 1, last_cycle + 1):
            created = datetime.date(cycle - 2, 10, 1) + datetime.timedelta(days=r.randint(0, 120))
            if created > today:
                break
            if created < plan.start + datetime.timedelta(days=90):
                continue  # just budgeted at initiation
            if cycle < next_cycle and cycle != last_cycle and r.random() < 0.1:
                continue  # no update this year; the last approved budget carries forward
            submitted = datetime.date(cycle - 1, 3, 1) + datetime.timedelta(days=r.randint(0, 60))
            approved = datetime.date(cycle - 1, 9, r.randint(8, 22))
            if approved <= today:
                versions.append((cycle, created, submitted, approved, B.REJECTED if r.random() < 0.03 else B.APPROVED))
            elif submitted <= today:
                versions.append((cycle, created, submitted, None, B.SUBMITTED))
            else:
                versions.append((cycle, created, None, None, B.DRAFT))
        return versions

    def project_budgets(self, plan):
        lines = self.estimate(plan)
        if not lines:
            return []
        r = self.rng
        fy0 = fiscal_year(plan.start)
        versions = self.cycles(plan, max(line[4] for line in lines))
        n = len(versions)
        # Cost growth between versions and schedule slip: earlier versions were cheaper and sooner.
        growth = [r.uniform(0.96, 1.12) for _ in range(n)]
        slip = r.choice([0, 0, 0, 1, 1, 2])
        optional_from = {i: r.randint(0, n - 1) for i, line in enumerate(lines) if line[6]}
        late_construction = fiscal_year(plan.construction_start) if plan.construction_start else None

        budgets, previous_total = [], None
        for k, (cycle, created, submitted, approved, status) in enumerate(versions):
            factor = 1.0
            for g in growth[k + 1 :]:
                factor /= g
            shift = round(slip * (n - 1 - k) / (n - 1)) if n > 1 else 0
            budget = Budget(
                project=plan.project,
                budget_year=cycle,
                status=status,
                prepared_by=plan.project.project_manager,
                submitted_date=submitted,
                approved_by=BOARD if status == B.APPROVED else "",
                approved_date=approved if status == B.APPROVED else None,
            )
            budget.demo_items = []
            for i, (category, description, total, first, last, shape, _optional) in enumerate(lines):
                if k < optional_from.get(i, 0):
                    continue
                first, last = max(fy0, first - shift), max(fy0, last - shift)
                item = BudgetLineItem(budget=budget, category=category, description=description)
                item.demo_amounts = [
                    BudgetAmount(line_item=item, fiscal_year=fy, amount=a)
                    for fy, a in self.spread(total * factor, first, max(first, last), shape).items()
                ]
                budget.demo_items.append(item)
            total = sum(a.amount for item in budget.demo_items for a in item.demo_amounts)
            if k == 0:
                budget.notes = "Initial budget at project initiation."
            else:
                in_construction = late_construction and cycle > late_construction
                reason = self.rng.choice(CONSTRUCTION_NOTES if in_construction else DESIGN_NOTES)
                change = (total - previous_total) / previous_total * 100 if previous_total else 0
                budget.notes = f"{reason} Total {change:+.0f}% from the FY{versions[k - 1][0]} budget."
            budget.created_on, budget.updated_on = created, approved or submitted or created
            if status != B.REJECTED:
                previous_total = total
            budgets.append(budget)

        approved = [b for b in budgets if b.status == B.APPROVED]
        for old, new in zip(approved, approved[1:]):
            old.status, old.superseded_by = B.SUPERSEDED, new
        return budgets

    # -- entry point --------------------------------------------------------------
    def run(self, plans):
        budgets = [b for plan in plans for b in self.project_budgets(plan)]
        for b in budgets:
            b.full_clean(
                exclude=["superseded_by"], validate_unique=False, validate_constraints=False
            )  # targets not saved yet
        Budget.objects.bulk_create(budgets, batch_size=500)
        items = [item for b in budgets for item in b.demo_items]
        for item in items:
            item.clean_fields(exclude=["budget"])
        BudgetLineItem.objects.bulk_create(items, batch_size=500)
        amounts = [a for item in items for a in item.demo_amounts]
        for a in amounts:
            a.clean_fields(exclude=["line_item"])
        BudgetAmount.objects.bulk_create(amounts, batch_size=1000)

        for b in budgets:
            b.created_at = self.aware(b.created_on)
            b.updated_at = max(b.created_at, self.aware(b.updated_on))
        Budget.objects.bulk_update(budgets, ["created_at", "updated_at"], batch_size=500)
        return {"budgets": len(budgets), "budget line items": len(items), "budget amounts": len(amounts)}

    def aware(self, d):
        moment = datetime.datetime.combine(min(d, self.today), datetime.time(8)) + datetime.timedelta(
            minutes=self.rng.randint(0, 540)
        )
        return min(timezone.make_aware(moment), timezone.now())


def extend(generator, plans):
    return BudgetGenerator(generator).run(plans)


pm_demo.EXTENSIONS.append(extend)
