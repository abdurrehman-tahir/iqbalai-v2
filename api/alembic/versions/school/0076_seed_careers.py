"""School migration: seed Pakistani careers vocabulary (T-189).

Revision ID: school_0076
Revises: school_0075
Create Date: 2026-10-03

Purpose: seed ~50 careers with Pakistani context + the concept keywords they
rely on (flow-6 §3.10). Reference data follows the repo convention (fixed
ids, idempotent insert — cf. school_0006 personas). Ids are uuid5(slug) so
every environment gets identical, stable ids for career_link_ids.
Risk: low — data only; ON CONFLICT DO NOTHING.
Reversible: yes (deletes exactly the seeded slugs)
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "school_0076"
down_revision: str = "school_0075"
branch_labels: tuple[()] = ()
depends_on: str | None = None

# Namespace label only (never resolved) — DNS-style name, not a URL.
_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "careers.iqbalai")

# (slug, name, sector, required_concepts) — frozen in this migration on purpose:
# later vocabulary changes ship as new migrations, never edits here.
_CAREERS: list[tuple[str, str, str, list[str]]] = [
    (
        "civil-engineer",
        "Civil Engineer",
        "Engineering",
        ["forces", "structures", "materials", "geometry"],
    ),
    (
        "mechanical-engineer",
        "Mechanical Engineer",
        "Engineering",
        ["forces", "motion", "energy", "thermodynamics"],
    ),
    (
        "electrical-engineer",
        "Electrical Engineer",
        "Engineering",
        ["electricity", "circuits", "magnetism", "energy"],
    ),
    (
        "electronics-engineer",
        "Electronics Engineer",
        "Engineering",
        ["circuits", "semiconductors", "signals"],
    ),
    (
        "software-engineer",
        "Software Engineer",
        "Technology",
        ["algorithms", "logic", "programming", "data"],
    ),
    (
        "chemical-engineer",
        "Chemical Engineer",
        "Engineering",
        ["chemical reactions", "thermodynamics", "stoichiometry"],
    ),
    (
        "petroleum-engineer",
        "Petroleum Engineer",
        "Energy",
        ["fluids", "pressure", "hydrocarbons", "geology"],
    ),
    (
        "aerospace-engineer",
        "Aerospace Engineer",
        "Engineering",
        ["aerodynamics", "forces", "motion", "gravity"],
    ),
    (
        "textile-engineer",
        "Textile Engineer",
        "Industry",
        ["materials", "fibers", "chemistry", "machines"],
    ),
    (
        "mining-engineer",
        "Mining Engineer",
        "Energy",
        ["geology", "minerals", "forces", "materials"],
    ),
    (
        "telecom-engineer",
        "Telecommunications Engineer",
        "Technology",
        ["waves", "signals", "electromagnetism"],
    ),
    (
        "agricultural-engineer",
        "Agricultural Engineer",
        "Agriculture",
        ["soil", "water", "machines", "energy"],
    ),
    ("doctor", "Doctor (MBBS)", "Health", ["human body", "cells", "biology", "chemistry"]),
    ("nurse", "Nurse", "Health", ["human body", "biology", "medicines"]),
    (
        "pharmacist",
        "Pharmacist",
        "Health",
        ["chemistry", "medicines", "chemical reactions", "biology"],
    ),
    ("dentist", "Dentist", "Health", ["human body", "biology", "materials"]),
    ("physiotherapist", "Physiotherapist", "Health", ["human body", "forces", "motion", "levers"]),
    (
        "medical-lab-technologist",
        "Medical Lab Technologist",
        "Health",
        ["microorganisms", "cells", "chemistry"],
    ),
    (
        "radiologic-technologist",
        "Radiologic Technologist",
        "Health",
        ["radiation", "waves", "human body"],
    ),
    ("nutritionist", "Nutritionist", "Health", ["nutrition", "digestion", "chemistry", "energy"]),
    ("agronomist", "Agronomist", "Agriculture", ["plants", "soil", "photosynthesis", "water"]),
    ("veterinarian", "Veterinarian", "Agriculture", ["animals", "biology", "microorganisms"]),
    ("fisheries-officer", "Fisheries Officer", "Agriculture", ["ecology", "water", "animals"]),
    (
        "environmental-scientist",
        "Environmental Scientist",
        "Environment",
        ["ecosystems", "pollution", "climate"],
    ),
    (
        "meteorologist",
        "Meteorologist (PMD)",
        "Environment",
        ["weather", "climate", "atmosphere", "pressure"],
    ),
    (
        "water-resources-engineer",
        "Water Resources Engineer",
        "Environment",
        ["water", "fluids", "pressure"],
    ),
    (
        "forestry-officer",
        "Forestry Officer",
        "Environment",
        ["plants", "ecosystems", "photosynthesis"],
    ),
    (
        "food-technologist",
        "Food Technologist",
        "Industry",
        ["chemistry", "microorganisms", "nutrition"],
    ),
    ("physicist", "Physicist", "Science & Research", ["forces", "energy", "waves", "electricity"]),
    (
        "chemist",
        "Chemist",
        "Science & Research",
        ["chemical reactions", "atoms", "bonding", "acids and bases"],
    ),
    (
        "biotechnologist",
        "Biotechnologist",
        "Science & Research",
        ["genetics", "cells", "microorganisms"],
    ),
    ("geologist", "Geologist", "Science & Research", ["rocks", "minerals", "earth", "earthquakes"]),
    (
        "space-scientist",
        "Space Scientist (SUPARCO)",
        "Science & Research",
        ["space", "gravity", "motion", "light"],
    ),
    ("statistician", "Statistician", "Science & Research", ["statistics", "probability", "data"]),
    (
        "data-scientist",
        "Data Scientist",
        "Technology",
        ["statistics", "data", "algorithms", "probability"],
    ),
    (
        "chartered-accountant",
        "Chartered Accountant",
        "Business & Finance",
        ["arithmetic", "percentages", "finance"],
    ),
    ("banker", "Banker", "Business & Finance", ["interest", "percentages", "finance"]),
    (
        "economist",
        "Economist",
        "Business & Finance",
        ["economics", "statistics", "supply and demand"],
    ),
    ("entrepreneur", "Entrepreneur", "Business & Finance", ["economics", "finance", "percentages"]),
    ("actuary", "Actuary", "Business & Finance", ["probability", "statistics", "interest"]),
    (
        "civil-servant",
        "Civil Servant (CSS Officer)",
        "Public Service",
        ["civics", "history", "governance"],
    ),
    ("lawyer", "Lawyer", "Public Service", ["law", "civics", "logic"]),
    ("journalist", "Journalist", "Media", ["language", "communication", "current affairs"]),
    ("teacher", "Teacher", "Education", ["communication", "language", "learning"]),
    ("architect", "Architect", "Design", ["geometry", "structures", "design", "materials"]),
    ("graphic-designer", "Graphic Designer", "Design", ["design", "geometry", "color", "light"]),
    ("urban-planner", "Urban Planner", "Design", ["geography", "population", "geometry"]),
    ("electrician", "Electrician", "Skilled Trades", ["electricity", "circuits", "safety"]),
    (
        "solar-technician",
        "Solar Energy Technician",
        "Energy",
        ["renewable energy", "electricity", "light"],
    ),
    (
        "auto-mechanic",
        "Automobile Mechanic",
        "Skilled Trades",
        ["engines", "motion", "energy", "machines"],
    ),
    ("pilot", "Pilot", "Aviation", ["aerodynamics", "navigation", "weather", "motion"]),
    ("surveyor", "Land Surveyor", "Engineering", ["geometry", "trigonometry", "maps"]),
]


def career_id(slug: str) -> str:
    return str(uuid.uuid5(_NS, slug))


def upgrade() -> None:
    careers = sa.table(
        "careers",
        sa.column("id", sa.String),
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("sector", sa.String),
        sa.column("required_concepts", postgresql.JSONB),
        schema="school",
    )
    stmt = postgresql.insert(careers).values(
        [
            {
                "id": career_id(slug),
                "slug": slug,
                "name": name,
                "sector": sector,
                "required_concepts": concepts,
            }
            for slug, name, sector, concepts in _CAREERS
        ]
    )
    op.execute(stmt.on_conflict_do_nothing(index_elements=["slug"]))


def downgrade() -> None:
    careers = sa.table("careers", sa.column("slug", sa.String), schema="school")
    op.execute(careers.delete().where(careers.c.slug.in_([c[0] for c in _CAREERS])))
