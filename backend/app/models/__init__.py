"""ORM model exports.

Importing this package registers every model class with ``Base.metadata`` so
``database.init_db()`` can create their tables.  Any new model must be
imported here.
"""
from app.models.career_document import CareerDocument
from app.models.career_profile import CareerProfile
from app.models.fit_analysis import FitAnalysis
from app.models.job_posting import JobPosting

__all__ = [
    "CareerDocument",
    "CareerProfile",
    "FitAnalysis",
    "JobPosting",
]
