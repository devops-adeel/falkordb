#!/usr/bin/env python3
"""
Arabic Tutor Entity Models for Graphiti
Defines custom Pydantic models for Arabic learning concepts
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from enum import Enum


class ProficiencyLevel(str, Enum):
    """Arabic proficiency levels"""
    BEGINNER = "beginner"
    ELEMENTARY = "elementary"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    FLUENT = "fluent"


class SkillType(str, Enum):
    """Language skill types"""
    READING = "reading"
    WRITING = "writing"
    SPEAKING = "speaking"
    LISTENING = "listening"
    GRAMMAR = "grammar"
    VOCABULARY = "vocabulary"


class Student(BaseModel):
    """Represents an Arabic language student"""
    student_name: str = Field(..., description="Student's name")
    proficiency_level: ProficiencyLevel = Field(ProficiencyLevel.BEGINNER, description="Current proficiency level")
    native_language: str = Field("English", description="Student's native language")
    learning_goals: List[str] = Field(default_factory=list, description="Student's learning goals")
    weekly_study_hours: Optional[float] = Field(None, description="Target weekly study hours")
    preferred_learning_style: Optional[str] = Field(None, description="Visual, auditory, kinesthetic, or reading/writing")
    start_date: Optional[str] = Field(None, description="When the student started learning (ISO format)")
    
    
class Lesson(BaseModel):
    """Represents an Arabic lesson or study session"""
    title: str = Field(..., description="Lesson title")
    skill_focus: SkillType = Field(..., description="Primary skill being taught")
    level: ProficiencyLevel = Field(..., description="Target proficiency level")
    duration_minutes: int = Field(30, description="Lesson duration in minutes")
    topics: List[str] = Field(default_factory=list, description="Topics covered in the lesson")
    materials_used: List[str] = Field(default_factory=list, description="Learning materials used")
    homework_assigned: Optional[str] = Field(None, description="Homework or practice assigned")
    completion_date: Optional[str] = Field(None, description="When the lesson was completed (ISO format)")


class VocabularyWord(BaseModel):
    """Represents an Arabic vocabulary word"""
    arabic_word: str = Field(..., description="The word in Arabic script")
    transliteration: str = Field(..., description="Romanized transliteration")
    english_meaning: str = Field(..., description="English translation")
    part_of_speech: Literal["noun", "verb", "adjective", "adverb", "preposition", "pronoun", "conjunction"] = Field(
        ..., description="Grammatical category"
    )
    root: Optional[str] = Field(None, description="Three-letter root (for Semitic word structure)")
    pattern: Optional[str] = Field(None, description="Morphological pattern (wazn)")
    usage_examples: List[str] = Field(default_factory=list, description="Example sentences")
    difficulty_level: ProficiencyLevel = Field(ProficiencyLevel.BEGINNER, description="Word difficulty level")
    memorization_status: Literal["new", "learning", "review", "mastered"] = Field("new", description="Learning status")
    last_reviewed: Optional[str] = Field(None, description="Last review date (ISO format)")


class GrammarRule(BaseModel):
    """Represents an Arabic grammar rule or concept"""
    rule_name: str = Field(..., description="Name of the grammar rule")
    category: Literal["morphology", "syntax", "phonology", "semantics"] = Field(
        ..., description="Grammar category"
    )
    description: str = Field(..., description="Explanation of the rule")
    level: ProficiencyLevel = Field(..., description="Difficulty level")
    examples: List[str] = Field(default_factory=list, description="Example applications")
    exceptions: List[str] = Field(default_factory=list, description="Notable exceptions to the rule")
    related_rules: List[str] = Field(default_factory=list, description="Related grammar concepts")
    mastery_level: float = Field(0.0, description="Student's mastery level (0-1)")


class Progress(BaseModel):
    """Represents learning progress and milestones"""
    student_name: str = Field(..., description="Student being tracked")
    skill_type: SkillType = Field(..., description="Skill being measured")
    current_level: ProficiencyLevel = Field(..., description="Current proficiency level")
    target_level: ProficiencyLevel = Field(..., description="Target proficiency level")
    progress_percentage: float = Field(0.0, description="Progress towards target (0-100)")
    milestones_completed: List[str] = Field(default_factory=list, description="Completed milestones")
    next_milestone: Optional[str] = Field(None, description="Next milestone to achieve")
    assessment_date: str = Field(..., description="Date of progress assessment (ISO format)")
    notes: Optional[str] = Field(None, description="Additional progress notes")


class PracticeSession(BaseModel):
    """Represents a practice or study session"""
    session_type: Literal["vocabulary", "grammar", "conversation", "reading", "writing", "listening"] = Field(
        ..., description="Type of practice"
    )
    duration_minutes: int = Field(..., description="Session duration")
    exercises_completed: int = Field(0, description="Number of exercises completed")
    accuracy_rate: Optional[float] = Field(None, description="Accuracy percentage (0-100)")
    words_practiced: List[str] = Field(default_factory=list, description="Vocabulary words practiced")
    grammar_points: List[str] = Field(default_factory=list, description="Grammar points covered")
    errors_made: List[str] = Field(default_factory=list, description="Common errors to review")
    session_date: str = Field(..., description="Session date (ISO format)")


# Edge type definitions for relationships between Arabic learning entities

class Studies(BaseModel):
    """Relationship: Student studies a lesson or topic"""
    started_date: str = Field(..., description="When study began (ISO format)")
    completion_status: Literal["not_started", "in_progress", "completed", "reviewed"] = Field(
        "not_started", description="Current status"
    )
    completion_percentage: float = Field(0.0, description="Completion percentage (0-100)")
    difficulty_rating: Optional[int] = Field(None, description="Student's difficulty rating (1-5)")
    notes: Optional[str] = Field(None, description="Study notes")


class CompletedLesson(BaseModel):
    """Relationship: Student completed a lesson"""
    completion_date: str = Field(..., description="Completion date (ISO format)")
    score: Optional[float] = Field(None, description="Lesson score (0-100)")
    time_spent_minutes: int = Field(..., description="Time spent on lesson")
    exercises_completed: int = Field(0, description="Number of exercises completed")
    review_needed: bool = Field(False, description="Whether review is recommended")


class Mastered(BaseModel):
    """Relationship: Student mastered a vocabulary word or grammar rule"""
    mastery_date: str = Field(..., description="Date of mastery (ISO format)")
    retention_score: float = Field(1.0, description="Retention score (0-1)")
    review_count: int = Field(0, description="Number of times reviewed")
    last_review_date: Optional[str] = Field(None, description="Last review date (ISO format)")
    confidence_level: float = Field(1.0, description="Confidence in mastery (0-1)")


class UsesInLesson(BaseModel):
    """Relationship: Lesson uses vocabulary or grammar"""
    emphasis_level: Literal["primary", "secondary", "mentioned"] = Field(
        "secondary", description="How prominently featured"
    )
    practice_exercises: int = Field(0, description="Number of practice exercises")
    introduced_as_new: bool = Field(False, description="Whether introduced as new material")


class RequiresGrammar(BaseModel):
    """Relationship: Vocabulary or concept requires grammar understanding"""
    prerequisite: bool = Field(True, description="Whether grammar is prerequisite")
    importance_level: Literal["essential", "helpful", "optional"] = Field(
        "helpful", description="Importance of the grammar"
    )


# Edge type mapping for Graphiti
ARABIC_EDGE_TYPE_MAP = {
    ("Student", "Lesson"): ["Studies", "CompletedLesson"],
    ("Student", "VocabularyWord"): ["Mastered"],
    ("Student", "GrammarRule"): ["Mastered"],
    ("Student", "Progress"): ["HasProgress"],
    ("Lesson", "VocabularyWord"): ["UsesInLesson"],
    ("Lesson", "GrammarRule"): ["UsesInLesson"],
    ("VocabularyWord", "GrammarRule"): ["RequiresGrammar"],
    ("Student", "PracticeSession"): ["Completed"],
}


# Entity and edge type dictionaries for Graphiti
ARABIC_ENTITY_TYPES = {
    "Student": Student,
    "Lesson": Lesson,
    "VocabularyWord": VocabularyWord,
    "GrammarRule": GrammarRule,
    "Progress": Progress,
    "PracticeSession": PracticeSession,
}


ARABIC_EDGE_TYPES = {
    "Studies": Studies,
    "CompletedLesson": CompletedLesson,
    "Mastered": Mastered,
    "UsesInLesson": UsesInLesson,
    "RequiresGrammar": RequiresGrammar,
}