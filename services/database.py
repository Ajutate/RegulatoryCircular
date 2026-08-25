"""
Database Service
=================
SQLAlchemy models and helper functions for:
  - Document history (upload + Excel export)
  - User management (Admin / Maker / Checker roles)
  - Custom prompt storage (Admin-editable prompts)
  - Document workflow (submit → review → approve/reject)
"""

import datetime
import json
import uuid
from typing import List, Dict, Any, Optional

from sqlalchemy import (
    create_engine, Column, String, Integer, DateTime,
    LargeBinary, Text, ForeignKey, Enum as SAEnum, Boolean
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from config.settings import get_settings

engine = create_engine(
    get_settings().database_url, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# ------------------------------------------------------------------ #
#  Models                                                             #
# ------------------------------------------------------------------ #

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # admin, maker, checker
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    prompt_type = Column(String, unique=True, nullable=False)  # "system" or "user"
    content = Column(Text, nullable=False)
    updated_by = Column(String, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)


class DocumentHistory(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, index=True)
    file_name = Column(String, nullable=False)
    circular_name = Column(String)
    upload_time = Column(DateTime, default=datetime.datetime.utcnow)
    paragraph_count = Column(Integer)
    excel_blob = Column(LargeBinary)

    # Workflow fields
    submitted_by = Column(String, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="draft")  # draft, pending_review, approved, rejected
    assigned_to = Column(String, ForeignKey("users.id"), nullable=True)
    reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)
    review_comment = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    submitter = relationship("User", foreign_keys=[submitted_by])
    assignee = relationship("User", foreign_keys=[assigned_to])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    paragraphs = relationship("Paragraph", back_populates="document", cascade="all, delete-orphan", order_by="Paragraph.paragraph_index")


class Paragraph(Base):
    __tablename__ = "paragraphs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    paragraph_index = Column(Integer, nullable=False)
    
    paragraph_text = Column(Text, nullable=False)
    para_type = Column(String, nullable=True)
    business_unit = Column(String, nullable=True)
    theme = Column(String, nullable=True)
    has_effective_date = Column(String, nullable=True)
    effective_date = Column(String, nullable=True)
    control_object_name = Column(String, nullable=True)
    actionable = Column(Text, nullable=True)
    level_1 = Column(String, nullable=True)
    level_2 = Column(String, nullable=True)
    level_3 = Column(String, nullable=True)
    
    status = Column(String, default="Pending") # Pending, Approved, Rejected
    needs_regeneration = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)

    document = relationship("DocumentHistory", back_populates="paragraphs")



# ------------------------------------------------------------------ #
#  Database Setup & Seed                                              #
# ------------------------------------------------------------------ #

def init_db():
    Base.metadata.create_all(bind=engine)
    # Safe migrations: add new columns if they don't exist yet
    for col_sql in [
        "ALTER TABLE paragraphs ADD COLUMN needs_regeneration BOOLEAN DEFAULT 0",
        "ALTER TABLE paragraphs ADD COLUMN is_deleted BOOLEAN DEFAULT 0",
    ]:
        try:
            with engine.connect() as conn:
                conn.execute(text(col_sql))
                conn.commit()
        except Exception:
            pass  # Column already exists
    init_sample_users()

def init_sample_users():
    import bcrypt
    
    db = SessionLocal()
    try:
        # Base roles
        default_users = [
            ("admin", "admin"),
            ("maker", "maker"),
            ("maker2", "maker"),
            ("maker3", "maker"),
            ("checker", "checker"),
            ("checker2", "checker"),
            ("checker3", "checker"),
        ]
        
        for username, role in default_users:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                try:
                    # Password is the same as the username for simplicity in testing
                    salt = bcrypt.gensalt()
                    hashed_pw = bcrypt.hashpw(username.encode('utf-8'), salt).decode('utf-8')
                    new_user = User(username=username, password_hash=hashed_pw, role=role)
                    db.add(new_user)
                    db.commit()
                except IntegrityError:
                    db.rollback()
    finally:
        db.close()


# ------------------------------------------------------------------ #
#  User helpers                                                       #
# ------------------------------------------------------------------ #

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Return user dict including password_hash."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user:
            return {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "password_hash": user.password_hash
            }
        return None
    finally:
        db.close()


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Return user dict or None."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return {"id": user.id, "username": user.username, "role": user.role}
        return None
    finally:
        db.close()


# ------------------------------------------------------------------ #
#  Prompt helpers                                                     #
# ------------------------------------------------------------------ #

def get_db_prompt(prompt_type: str) -> Optional[str]:
    """Return admin-edited prompt content from DB, or None if not set."""
    db = SessionLocal()
    try:
        p = db.query(Prompt).filter(Prompt.prompt_type == prompt_type).first()
        return p.content if p else None
    finally:
        db.close()


def save_prompt(prompt_type: str, content: str, user_id: str) -> Dict[str, Any]:
    """Save or update a prompt in the DB."""
    db = SessionLocal()
    try:
        p = db.query(Prompt).filter(Prompt.prompt_type == prompt_type).first()
        now = datetime.datetime.utcnow()
        if p:
            p.content = content
            p.updated_by = user_id
            p.updated_at = now
        else:
            p = Prompt(
                prompt_type=prompt_type,
                content=content,
                updated_by=user_id,
                updated_at=now,
            )
            db.add(p)
        db.commit()
        return {"prompt_type": prompt_type, "updated_at": now.isoformat()}
    finally:
        db.close()


def delete_prompt(prompt_type: str) -> bool:
    """Delete a custom prompt so the code default is used again."""
    db = SessionLocal()
    try:
        p = db.query(Prompt).filter(Prompt.prompt_type == prompt_type).first()
        if p:
            db.delete(p)
            db.commit()
            return True
        return False
    finally:
        db.close()


def get_all_prompts() -> Dict[str, Optional[str]]:
    """Return dict of all stored prompts keyed by type."""
    db = SessionLocal()
    try:
        prompts = db.query(Prompt).all()
        return {p.prompt_type: p.content for p in prompts}
    finally:
        db.close()


# ------------------------------------------------------------------ #
#  Document / History helpers                                         #
# ------------------------------------------------------------------ #

def save_document(
    doc_id: str,
    file_name: str,
    circular_name: str,
    paragraph_count: int,
    excel_blob: Optional[bytes] = None,
    submitted_by: Optional[str] = None,
    analysis_results: Optional[List[Dict[str, Any]]] = None,
    paragraphs: Optional[List[str]] = None,
):
    """Save a processed document and its Excel export to the database."""
    db = SessionLocal()
    try:
        db_doc = DocumentHistory(
            id=doc_id,
            file_name=file_name,
            circular_name=circular_name,
            upload_time=datetime.datetime.utcnow(),
            paragraph_count=paragraph_count,
            excel_blob=excel_blob,
            submitted_by=submitted_by,
            status="draft",
        )
        db.add(db_doc)
        
        if analysis_results and paragraphs:
            for idx, (result, text) in enumerate(zip(analysis_results, paragraphs)):
                para = Paragraph(
                    document_id=doc_id,
                    paragraph_index=idx,
                    paragraph_text=text,
                    para_type=result.get("para_type"),
                    business_unit=result.get("business_unit"),
                    theme=result.get("theme"),
                    has_effective_date=result.get("has_effective_date"),
                    effective_date=result.get("effective_date"),
                    control_object_name=result.get("control_object_name"),
                    actionable=result.get("actionable"),
                    level_1=result.get("level_1"),
                    level_2=result.get("level_2"),
                    level_3=result.get("level_3"),
                    status=result.get("status", "Pending")
                )
                db.add(para)
                
        db.commit()
    finally:
        db.close()


def get_history(user_id: Optional[str] = None, role: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve document history. Makers see only their own docs."""
    db = SessionLocal()
    try:
        query = db.query(DocumentHistory).order_by(DocumentHistory.upload_time.desc())
        
        if role == "maker" and user_id:
            query = query.filter(DocumentHistory.submitted_by == user_id)
        elif role == "checker" and user_id:
            from sqlalchemy import or_, and_
            
            # Condition 1: pending_review (and either unassigned or assigned to this checker)
            cond1 = and_(
                DocumentHistory.status == "pending_review",
                or_(DocumentHistory.assigned_to == None, DocumentHistory.assigned_to == user_id)
            )
            # Condition 2: approved/rejected and reviewed by this checker
            cond2 = and_(
                DocumentHistory.status.in_(["approved", "rejected"]),
                DocumentHistory.reviewed_by == user_id
            )
            
            query = query.filter(or_(cond1, cond2))
            
        docs = query.all()
        return [
            {
                "id": doc.id,
                "file_name": doc.file_name,
                "circular_name": doc.circular_name,
                "upload_time": doc.upload_time.isoformat() if doc.upload_time else "",
                "paragraph_count": doc.paragraph_count,
                "status": doc.status or "draft",
                "submitted_by": doc.submitted_by,
                "submitter_name": doc.submitter.username if doc.submitter else "",
                "reviewed_by": doc.reviewed_by,
                "reviewer_name": doc.reviewer.username if doc.reviewer else "",
                "review_comment": doc.review_comment or "",
                "reviewed_at": doc.reviewed_at.isoformat() if doc.reviewed_at else "",
            }
            for doc in docs
        ]
    finally:
        db.close()


def get_excel(doc_id: str) -> Optional[bytes]:
    """Retrieve the Excel BLOB for a specific document ID."""
    db = SessionLocal()
    try:
        doc = db.query(DocumentHistory).filter(DocumentHistory.id == doc_id).first()
        return doc.excel_blob if doc else None
    finally:
        db.close()


def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve full document record including analysis results and paragraphs."""
    db = SessionLocal()
    try:
        doc = db.query(DocumentHistory).filter(DocumentHistory.id == doc_id).first()
        if not doc:
            return None
            
        paragraphs_data = []
        analysis_data = []
        for p in doc.paragraphs:
            if p.is_deleted:
                continue
            paragraphs_data.append(p.paragraph_text)
            analysis_data.append({
                "paragraph_text": p.paragraph_text,
                "para_type": p.para_type,
                "business_unit": p.business_unit,
                "theme": p.theme,
                "has_effective_date": p.has_effective_date,
                "effective_date": p.effective_date,
                "control_object_name": p.control_object_name,
                "actionable": p.actionable,
                "level_1": p.level_1,
                "level_2": p.level_2,
                "level_3": p.level_3,
                "status": p.status,
                "needs_regeneration": bool(p.needs_regeneration)
            })
            
        return {
            "id": doc.id,
            "file_name": doc.file_name,
            "circular_name": doc.circular_name,
            "upload_time": doc.upload_time.isoformat() if doc.upload_time else "",
            "paragraph_count": doc.paragraph_count,
            "status": doc.status or "draft",
            "submitted_by": doc.submitted_by,
            "submitter_name": doc.submitter.username if doc.submitter else "",
            "review_comment": doc.review_comment or "",
            "analysis_results_json": json.dumps(analysis_data) if analysis_data else None,
            "paragraphs_json": json.dumps(paragraphs_data) if paragraphs_data else None,
        }
    finally:
        db.close()


# ------------------------------------------------------------------ #
#  Workflow helpers                                                   #
# ------------------------------------------------------------------ #

def submit_for_review(doc_id: str, user_id: str) -> bool:
    """Maker submits a document for Checker review."""
    db = SessionLocal()
    try:
        doc = db.query(DocumentHistory).filter(DocumentHistory.id == doc_id).first()
        if not doc:
            return False
        doc.status = "pending_review"
        doc.submitted_by = user_id
        db.commit()
        return True
    finally:
        db.close()


def get_unassigned_count() -> int:
    """Return count of unassigned documents pending review."""
    db = SessionLocal()
    try:
        return (
            db.query(DocumentHistory)
            .filter(DocumentHistory.status == "pending_review")
            .filter(DocumentHistory.assigned_to == None)
            .count()
        )
    finally:
        db.close()

def get_checker_queue(checker_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """Return documents pending review, split by unassigned and my_queue."""
    db = SessionLocal()
    try:
        docs = (
            db.query(DocumentHistory)
            .filter(DocumentHistory.status == "pending_review")
            .order_by(DocumentHistory.upload_time.desc())
            .all()
        )
        
        unassigned = []
        my_queue = []
        
        for doc in docs:
            item = {
                "id": doc.id,
                "file_name": doc.file_name,
                "circular_name": doc.circular_name,
                "upload_time": doc.upload_time.isoformat() if doc.upload_time else "",
                "paragraph_count": doc.paragraph_count,
                "status": doc.status,
                "submitter_name": doc.submitter.username if doc.submitter else "",
                "assigned_to": doc.assigned_to,
            }
            if not doc.assigned_to:
                unassigned.append(item)
            elif doc.assigned_to == checker_id:
                my_queue.append(item)
                
        return {"unassigned": unassigned, "my_queue": my_queue}
    finally:
        db.close()


def claim_document(doc_id: str, checker_id: str) -> bool:
    """Checker claims an unassigned document."""
    db = SessionLocal()
    try:
        doc = db.query(DocumentHistory).filter(DocumentHistory.id == doc_id).first()
        if not doc or doc.status != "pending_review":
            return False
        if doc.assigned_to is not None:
            return False  # Already claimed
        doc.assigned_to = checker_id
        db.commit()
        return True
    finally:
        db.close()


def approve_document(doc_id: str, reviewer_id: str) -> bool:
    """Checker approves a document."""
    db = SessionLocal()
    try:
        doc = db.query(DocumentHistory).filter(DocumentHistory.id == doc_id).first()
        if not doc or doc.assigned_to != reviewer_id:
            return False
        doc.status = "approved"
        doc.reviewed_by = reviewer_id
        doc.reviewed_at = datetime.datetime.utcnow()
        doc.review_comment = None
        db.commit()
        return True
    finally:
        db.close()


def reject_document(doc_id: str, reviewer_id: str, comment: str) -> bool:
    """Checker rejects a document with a comment."""
    db = SessionLocal()
    try:
        doc = db.query(DocumentHistory).filter(DocumentHistory.id == doc_id).first()
        if not doc or doc.assigned_to != reviewer_id:
            return False
        doc.status = "rejected"
        doc.reviewed_by = reviewer_id
        doc.reviewed_at = datetime.datetime.utcnow()
        doc.review_comment = comment
        db.commit()
        return True
    finally:
        db.close()


def update_document_excel(doc_id: str, excel_blob: bytes) -> bool:
    """Update the Excel blob after re-analysis or approval."""
    db = SessionLocal()
    try:
        doc = db.query(DocumentHistory).filter(DocumentHistory.id == doc_id).first()
        if not doc:
            return False
        doc.excel_blob = excel_blob
        db.commit()
        return True
    finally:
        db.close()


def update_paragraph_result(doc_id: str, idx: int, result_json: dict) -> bool:
    """Update a specific paragraph result in the database."""
    db = SessionLocal()
    try:
        para = db.query(Paragraph).filter(
            Paragraph.document_id == doc_id,
            Paragraph.paragraph_index == idx
        ).first()
        
        if not para:
            return False
            
        if "para_type" in result_json: para.para_type = result_json["para_type"]
        if "business_unit" in result_json: para.business_unit = result_json["business_unit"]
        if "theme" in result_json: para.theme = result_json["theme"]
        if "has_effective_date" in result_json: para.has_effective_date = result_json["has_effective_date"]
        if "effective_date" in result_json: para.effective_date = result_json["effective_date"]
        if "control_object_name" in result_json: para.control_object_name = result_json["control_object_name"]
        if "actionable" in result_json: para.actionable = result_json["actionable"]
        if "level_1" in result_json: para.level_1 = result_json["level_1"]
        if "level_2" in result_json: para.level_2 = result_json["level_2"]
        if "level_3" in result_json: para.level_3 = result_json["level_3"]
        if "status" in result_json: para.status = result_json["status"]
        if "needs_regeneration" in result_json: para.needs_regeneration = result_json["needs_regeneration"]

        db.commit()
        return True
    finally:
        db.close()

def update_document_results(doc_id: str, analysis_results: List[Dict[str, Any]]) -> bool:
    """Update all results for a document after a re-analysis."""
    db = SessionLocal()
    try:
        doc = db.query(DocumentHistory).filter(DocumentHistory.id == doc_id).first()
        if not doc:
            return False
            
        for p in doc.paragraphs:
            db.delete(p)
            
        for idx, result in enumerate(analysis_results):
            pass
            
        return False
    finally:
        db.close()


# ------------------------------------------------------------------ #
#  Paragraph Merge / Split / Reorder helpers                          #
# ------------------------------------------------------------------ #

def _reindex_paragraphs(db, doc_id: str) -> None:
    """Reassign paragraph_index values 0, 1, 2, ... in order (skipping soft-deleted)."""
    paras = (
        db.query(Paragraph)
        .filter(Paragraph.document_id == doc_id, Paragraph.is_deleted == False)
        .order_by(Paragraph.paragraph_index)
        .all()
    )
    for new_idx, para in enumerate(paras):
        para.paragraph_index = new_idx

    # Update document paragraph count
    doc = db.query(DocumentHistory).filter(DocumentHistory.id == doc_id).first()
    if doc:
        doc.paragraph_count = len(paras)


def delete_paragraph(doc_id: str, idx: int) -> bool:
    """
    Soft-delete a single paragraph by index.

    - Marks the paragraph as is_deleted=True.
    - Reindexes remaining (non-deleted) paragraphs.
    - Returns True on success.
    """
    db = SessionLocal()
    try:
        para = (
            db.query(Paragraph)
            .filter(Paragraph.document_id == doc_id, Paragraph.paragraph_index == idx)
            .first()
        )
        if not para:
            return False

        para.is_deleted = True
        db.flush()
        _reindex_paragraphs(db, doc_id)
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()




def merge_paragraphs(doc_id: str, indices: List[int]) -> Optional[Dict[str, Any]]:
    """
    Merge 2+ paragraphs into one.

    - Concatenates text in index order.
    - Deletes old rows, inserts one new row at the lowest index.
    - Reindexes all paragraphs.
    - Returns the new paragraph dict (text only, no analysis yet).
    """
    if len(indices) < 2:
        return None

    indices_sorted = sorted(indices)
    db = SessionLocal()
    try:
        paras = (
            db.query(Paragraph)
            .filter(Paragraph.document_id == doc_id, Paragraph.paragraph_index.in_(indices_sorted))
            .order_by(Paragraph.paragraph_index)
            .all()
        )
        if len(paras) != len(indices_sorted):
            return None

        # Build merged text
        merged_text = " ".join(p.paragraph_text for p in paras)
        new_index = indices_sorted[0]

        # Delete old paragraphs
        for p in paras:
            db.delete(p)
        db.flush()

        # Insert merged paragraph
        new_para = Paragraph(
            document_id=doc_id,
            paragraph_index=new_index,
            paragraph_text=merged_text,
            status="Pending",
            needs_regeneration=True,
        )
        db.add(new_para)
        db.flush()

        # Reindex
        _reindex_paragraphs(db, doc_id)
        db.commit()

        return {
            "paragraph_id": new_para.id,
            "paragraph_index": new_para.paragraph_index,
            "paragraph_text": merged_text,
        }
    except Exception:
        db.rollback()
        return None
    finally:
        db.close()


def split_paragraph(doc_id: str, idx: int, new_parts: List[str]) -> Optional[List[Dict[str, Any]]]:
    """
    Split one paragraph into multiple parts.

    - Deletes the old row, inserts new rows for each part.
    - Reindexes all paragraphs.
    - Returns a list of dicts with the new paragraph texts.
    """
    db = SessionLocal()
    try:
        para = (
            db.query(Paragraph)
            .filter(Paragraph.document_id == doc_id, Paragraph.paragraph_index == idx)
            .first()
        )
        if not para:
            return None

        if len(new_parts) < 1:
            return None

        old_index = para.paragraph_index
        db.delete(para)
        db.flush()

        # Insert new paragraphs starting at the old index
        new_paras = []
        for i, part in enumerate(new_parts):
            new_para = Paragraph(
                document_id=doc_id,
                paragraph_index=old_index + i,
                paragraph_text=part,
                status="Pending",
                needs_regeneration=True,
            )
            db.add(new_para)
            new_paras.append(new_para)
            
        db.flush()
        _reindex_paragraphs(db, doc_id)
        db.commit()

        return [
            {
                "paragraph_id": p.id,
                "paragraph_index": p.paragraph_index,
                "paragraph_text": p.paragraph_text,
            }
            for p in new_paras
        ]
    except Exception:
        db.rollback()
        return None
    finally:
        db.close()


def reorder_paragraphs(doc_id: str, new_order: List[int]) -> bool:
    """
    Reorder paragraphs according to `new_order`.

    `new_order` is a list of current paragraph_index values in the desired
    new sequence.  E.g. [2, 0, 1, 3] means "paragraph currently at index 2
    should become the first one."
    """
    db = SessionLocal()
    try:
        paras = (
            db.query(Paragraph)
            .filter(Paragraph.document_id == doc_id)
            .order_by(Paragraph.paragraph_index)
            .all()
        )

        if len(new_order) != len(paras):
            return False

        # Build a map: old_index -> Paragraph object
        para_map = {p.paragraph_index: p for p in paras}

        # Use temporary negative indices to avoid unique-constraint clashes
        for tmp_idx, old_idx in enumerate(new_order):
            if old_idx not in para_map:
                return False
            para_map[old_idx].paragraph_index = -(tmp_idx + 1)
        db.flush()

        # Now set to the actual new indices
        for tmp_idx, old_idx in enumerate(new_order):
            para_map[old_idx].paragraph_index = tmp_idx
        db.commit()

        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()
