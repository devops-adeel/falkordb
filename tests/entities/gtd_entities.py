#!/usr/bin/env python3
"""
GTD Coach Entity Models for Graphiti
Adapted from gtd-coach project for testing with FalkorDB
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from enum import Enum


class Priority(str, Enum):
    """GTD Priority levels"""
    A = "A"  # Critical/Urgent
    B = "B"  # Important
    C = "C"  # Nice to have
    NONE = "None"


class Energy(str, Enum):
    """Energy levels for tasks"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ProjectStatus(str, Enum):
    """GTD Project status"""
    ACTIVE = "active"
    SOMEDAY = "someday"
    COMPLETED = "completed"
    STALLED = "stalled"


class Task(BaseModel):
    """Represents a GTD Task/Next Action"""
    description: str = Field(..., description="Clear description of the task")
    project: Optional[str] = Field(None, description="Associated project name")
    context: str = Field("@anywhere", description="Context where task can be done (@home, @office, @computer, @phone)")
    priority: Priority = Field(Priority.NONE, description="Priority level")
    energy_required: Energy = Field(Energy.MEDIUM, description="Energy level required")
    time_estimate: Optional[int] = Field(None, description="Estimated time in minutes")
    waiting_for: Optional[str] = Field(None, description="Person or event this is waiting on")
    delegated_to: Optional[str] = Field(None, description="Person this is delegated to")
    due_date: Optional[str] = Field(None, description="Due date if applicable (ISO format)")
    completed: bool = Field(False, description="Whether the task is completed")


class Project(BaseModel):
    """Represents a GTD Project"""
    project_name: str = Field(..., description="Project name")
    status: ProjectStatus = Field(ProjectStatus.ACTIVE, description="Current project status")
    area_of_focus: Optional[str] = Field(None, description="Related area of focus or responsibility")
    next_action: Optional[str] = Field(None, description="The very next physical action")
    outcome: Optional[str] = Field(None, description="Desired outcome or successful completion criteria")
    deadline: Optional[str] = Field(None, description="Project deadline if applicable (ISO format)")
    review_frequency: Optional[str] = Field("weekly", description="How often to review this project")
    notes: Optional[str] = Field(None, description="Additional project notes")


class Context(BaseModel):
    """Represents a GTD Context (location/tool/person)"""
    context_name: str = Field(..., description="Context name (e.g., @home, @office, @computer)")
    available_time: Optional[int] = Field(None, description="Available time in this context (minutes)")
    energy_level: Energy = Field(Energy.MEDIUM, description="Current energy level in this context")
    tools_available: List[str] = Field(default_factory=list, description="Tools/resources available")
    active: bool = Field(True, description="Whether this context is currently active/available")
    location: Optional[str] = Field(None, description="Physical location if applicable")


class NextAction(BaseModel):
    """Represents the next action for a project"""
    action: str = Field(..., description="Description of the next action")
    project_name: str = Field(..., description="Associated project")
    context_required: str = Field("@anywhere", description="Context needed")
    estimated_minutes: Optional[int] = Field(None, description="Time estimate")
    energy_required: Energy = Field(Energy.MEDIUM, description="Energy needed")
    blocked: bool = Field(False, description="Whether this action is blocked")
    blocking_reason: Optional[str] = Field(None, description="Reason if blocked")


class Review(BaseModel):
    """Represents a GTD weekly/periodic review"""
    review_type: Literal["weekly", "monthly", "quarterly", "annual"] = Field("weekly", description="Type of review")
    review_date: str = Field(..., description="Date of review (ISO format)")
    projects_reviewed: int = Field(0, description="Number of projects reviewed")
    tasks_created: int = Field(0, description="New tasks created")
    tasks_completed: int = Field(0, description="Tasks marked complete")
    someday_items: int = Field(0, description="Items moved to someday/maybe")
    duration_minutes: Optional[int] = Field(None, description="Review duration")
    notes: Optional[str] = Field(None, description="Review notes and insights")


class AreaOfFocus(BaseModel):
    """Represents an Area of Focus/Responsibility"""
    area_name: str = Field(..., description="Area name (e.g., Health, Finance, Career)")
    description: Optional[str] = Field(None, description="Description of this area")
    projects: List[str] = Field(default_factory=list, description="Projects in this area")
    maintenance_tasks: List[str] = Field(default_factory=list, description="Recurring maintenance tasks")
    review_frequency: str = Field("weekly", description="How often to review this area")
    standards: List[str] = Field(default_factory=list, description="Standards to maintain")


class InboxItem(BaseModel):
    """Represents an item in the GTD inbox"""
    content: str = Field(..., description="The raw captured thought/task/idea")
    capture_date: str = Field(..., description="When captured (ISO format)")
    source: Literal["mindsweep", "email", "phone", "meeting", "idea"] = Field(
        "mindsweep", description="Where this came from"
    )
    processed: bool = Field(False, description="Whether processed through GTD workflow")
    outcome: Optional[Literal["task", "project", "reference", "trash", "someday"]] = Field(
        None, description="Processing outcome"
    )


# Edge type definitions for GTD relationships

class BelongsTo(BaseModel):
    """Relationship: Task/NextAction belongs to Project"""
    is_next_action: bool = Field(False, description="Whether this is THE next action")
    sequence_order: Optional[int] = Field(None, description="Order in project sequence")
    dependency: Optional[str] = Field(None, description="What this depends on")


class BlockedBy(BaseModel):
    """Relationship: Task is blocked by another task"""
    blocking_reason: str = Field(..., description="Why this is blocked")
    estimated_unblock_date: Optional[str] = Field(None, description="When expected to unblock")
    is_hard_dependency: bool = Field(True, description="Whether this is a hard block")


class HasNextAction(BaseModel):
    """Relationship: Project has a next action"""
    is_current: bool = Field(True, description="Whether this is the current next action")
    created_date: str = Field(..., description="When this became next action")


class RequiresContext(BaseModel):
    """Relationship: Task requires a specific context"""
    exclusive: bool = Field(False, description="Whether ONLY this context works")
    preferred: bool = Field(True, description="Whether this is preferred context")


class InArea(BaseModel):
    """Relationship: Project is in an area of focus"""
    primary: bool = Field(True, description="Whether this is primary area")
    alignment_score: Optional[float] = Field(None, description="How well aligned (0-1)")


class ProcessedInto(BaseModel):
    """Relationship: InboxItem was processed into task/project"""
    processing_date: str = Field(..., description="When processed (ISO format)")
    processing_notes: Optional[str] = Field(None, description="Notes from processing")


# Edge type mapping for Graphiti
GTD_EDGE_TYPE_MAP = {
    ("Task", "Project"): ["BelongsTo"],
    ("NextAction", "Project"): ["BelongsTo"],
    ("Task", "Task"): ["BlockedBy"],
    ("Task", "Context"): ["RequiresContext"],
    ("NextAction", "Context"): ["RequiresContext"],
    ("Project", "NextAction"): ["HasNextAction"],
    ("Project", "AreaOfFocus"): ["InArea"],
    ("InboxItem", "Task"): ["ProcessedInto"],
    ("InboxItem", "Project"): ["ProcessedInto"],
}


# Entity and edge type dictionaries for Graphiti
GTD_ENTITY_TYPES = {
    "Task": Task,
    "Project": Project,
    "Context": Context,
    "NextAction": NextAction,
    "Review": Review,
    "AreaOfFocus": AreaOfFocus,
    "InboxItem": InboxItem,
}


GTD_EDGE_TYPES = {
    "BelongsTo": BelongsTo,
    "BlockedBy": BlockedBy,
    "HasNextAction": HasNextAction,
    "RequiresContext": RequiresContext,
    "InArea": InArea,
    "ProcessedInto": ProcessedInto,
}