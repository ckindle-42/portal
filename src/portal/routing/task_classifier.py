"""
Task Classifier - Heuristic-based query analysis for optimal model selection
Uses pattern matching for <10ms classification
"""

import re
from dataclasses import dataclass, field
from enum import Enum


class TaskComplexity(Enum):
    """Task complexity levels"""

    TRIVIAL = "trivial"  # "hi", "thanks", simple greetings
    SIMPLE = "simple"  # Basic questions, short answers
    MODERATE = "moderate"  # Multi-step reasoning, longer content
    COMPLEX = "complex"  # Code generation, detailed analysis
    EXPERT = "expert"  # Advanced reasoning, long-form content


class TaskCategory(Enum):
    """Task categories"""

    GREETING = "greeting"
    QUESTION = "question"
    CODE = "code"
    MATH = "math"
    CREATIVE = "creative"
    ANALYSIS = "analysis"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    TOOL_USE = "tool_use"
    GENERAL = "general"


@dataclass
class TaskClassification:
    """Complete task classification result"""

    complexity: TaskComplexity
    category: TaskCategory
    estimated_tokens: int
    requires_reasoning: bool
    requires_code: bool
    requires_math: bool
    is_multi_turn: bool
    confidence: float  # 0.0-1.0
    patterns_matched: list[str] = field(default_factory=list)


class TaskClassifier:
    """
    Heuristic-based task classifier

    Uses pattern matching for instant classification (<10ms)
    No LLM calls needed - pure rule-based for speed
    """

    # Greeting patterns
    GREETING_PATTERNS = [
        r"^(hi|hello|hey|yo|sup|greetings|howdy|hiya)\b",
        r"^(good\s+)?(morning|afternoon|evening|night)\b",
        r"^(what\'?s\s+up|how\s+are\s+you|how\'?s\s+it\s+going)",
        r"^(thanks|thank\s+you|thx|ty|cheers)\b",
        r"^(bye|goodbye|see\s+you|later|cya)\b",
    ]

    # Code patterns
    CODE_PATTERNS = [
        r"\b(code|program|script|function|class|method)\b",
        r"\b(python|javascript|java|cpp|rust|go|ruby|swift)\b",
        r"\b(bug|error|exception|debug|fix|issue)\b",
        r"\b(implement|write|create|build|develop)\s+(a\s+)?(code|function|class|script)",
        r"```",  # Code blocks
        r"\b(api|endpoint|request|response|http|rest|graphql)\b",
        r"\b(database|sql|query|select|insert|update|delete)\b",
        r"\b(git|commit|branch|merge|pull|push)\b",
    ]

    # Math patterns
    MATH_PATTERNS = [
        r"\b(calculate|compute|solve|evaluate|simplify)\b",
        r"\b(equation|formula|integral|derivative|matrix)\b",
        r"\b(sum|product|average|mean|median|variance)\b",
        r"[\d+\-*/^=()]+",  # Math expressions
        r"\b(algebra|calculus|geometry|statistics|probability)\b",
        r"\b(proof|theorem|lemma|axiom)\b",
    ]

    # Analysis patterns
    ANALYSIS_PATTERNS = [
        r"\b(analyze|analysis|examine|evaluate|assess)\b",
        r"\b(compare|contrast|difference|similarity)\b",
        r"\b(pros\s+and\s+cons|advantages|disadvantages)\b",
        r"\b(review|critique|assess|evaluate)\b",
        r"\b(explain|describe|elaborate|detail)\b",
    ]

    # Creative patterns
    CREATIVE_PATTERNS = [
        r"\b(write|compose|create|generate)\s+(a\s+)?(story|poem|essay|article)",
        r"\b(creative|imaginative|fictional|fantasy)\b",
        r"\b(character|plot|setting|narrative)\b",
        r"\b(brainstorm|ideas|suggest|recommend)\b",
    ]

    # Tool use patterns
    TOOL_PATTERNS = [
        r"\b(generate\s+)?(qr\s+code|barcode)\b",
        r"\b(convert|transform)\s+.+\s+(to|into)\b",
        r"\b(compress|decompress|zip|unzip|archive)\b",
        r"\b(search|find|lookup|query)\b",
        r"\b(schedule|reminder|timer|alarm)\b",
        r"\b(download|fetch|get|retrieve)\b",
        r"\b(plot|graph|chart|visualize)\b",
        r"\b(transcribe|speech|audio|voice)\b",
    ]

    # Question patterns
    QUESTION_PATTERNS = [
        r"\?$",  # Ends with question mark
        r"^(what|who|when|where|why|how|which|can|could|would|should|is|are|do|does|did)",
        r"\b(explain|describe|tell\s+me|show\s+me)\b",
    ]

    def __init__(self) -> None:
        # Compile patterns for efficiency
        self._greeting_re = [re.compile(p, re.IGNORECASE) for p in self.GREETING_PATTERNS]
        self._code_re = [re.compile(p, re.IGNORECASE) for p in self.CODE_PATTERNS]
        self._math_re = [re.compile(p, re.IGNORECASE) for p in self.MATH_PATTERNS]
        self._analysis_re = [re.compile(p, re.IGNORECASE) for p in self.ANALYSIS_PATTERNS]
        self._creative_re = [re.compile(p, re.IGNORECASE) for p in self.CREATIVE_PATTERNS]
        self._tool_re = [re.compile(p, re.IGNORECASE) for p in self.TOOL_PATTERNS]
        self._question_re = [re.compile(p, re.IGNORECASE) for p in self.QUESTION_PATTERNS]

    def _match_all_patterns(self, query: str) -> dict[str, int]:
        """Return match counts for each pattern group against query."""
        return {
            "code": sum(1 for p in self._code_re if p.search(query)),
            "math": sum(1 for p in self._math_re if p.search(query)),
            "analysis": sum(1 for p in self._analysis_re if p.search(query)),
            "creative": sum(1 for p in self._creative_re if p.search(query)),
            "tool": sum(1 for p in self._tool_re if p.search(query)),
        }

    def classify(self, query: str) -> TaskClassification:
        """Classify a query using heuristics. Returns classification in <10ms."""
        query = query.strip()
        word_count = len(query.split())
        char_count = len(query)
        patterns_matched: list[str] = []

        # Greetings: fast-path before full pattern scan
        if word_count <= 5 and any(p.search(query.lower()) for p in self._greeting_re):
            patterns_matched.append("greeting")
            return TaskClassification(
                complexity=TaskComplexity.TRIVIAL,
                category=TaskCategory.GREETING,
                estimated_tokens=20,
                requires_reasoning=False,
                requires_code=False,
                requires_math=False,
                is_multi_turn=False,
                confidence=0.95,
                patterns_matched=patterns_matched,
            )

        counts = self._match_all_patterns(query)
        patterns_matched.extend(f"{k}:{v}" for k, v in counts.items() if v > 0)

        category = self._detect_category(counts, query)
        complexity = self._estimate_complexity(
            word_count,
            char_count,
            counts["code"],
            counts["math"],
            counts["analysis"],
            counts["creative"],
        )
        estimated_tokens = self._estimate_output_tokens(complexity, category)

        return TaskClassification(
            complexity=complexity,
            category=category,
            estimated_tokens=estimated_tokens,
            requires_reasoning=complexity in [TaskComplexity.COMPLEX, TaskComplexity.EXPERT],
            requires_code=counts["code"] >= 1,
            requires_math=counts["math"] >= 1,
            is_multi_turn=False,
            confidence=0.8 if patterns_matched else 0.5,
            patterns_matched=patterns_matched,
        )

    def _detect_category(self, counts: dict, query: str) -> "TaskCategory":
        """Map pattern match counts to a task category."""
        if counts["code"] >= 2:
            return TaskCategory.CODE
        if counts["math"] >= 2:
            return TaskCategory.MATH
        if counts["tool"] >= 1:
            return TaskCategory.TOOL_USE
        if counts["creative"] >= 2:
            return TaskCategory.CREATIVE
        if counts["analysis"] >= 2:
            return TaskCategory.ANALYSIS
        if any(p.search(query) for p in self._question_re):
            return TaskCategory.QUESTION
        return TaskCategory.GENERAL

    def _estimate_complexity(
        self,
        word_count: int,
        char_count: int,
        code_matches: int,
        math_matches: int,
        analysis_matches: int,
        creative_matches: int,
    ) -> TaskComplexity:
        """Estimate task complexity"""

        # Very short = trivial
        if word_count <= 3:
            return TaskComplexity.TRIVIAL

        # Short simple questions
        if word_count <= 10 and code_matches == 0 and math_matches == 0:
            return TaskComplexity.SIMPLE

        # Code generation is complex
        if code_matches >= 3:
            return TaskComplexity.COMPLEX

        # Detailed analysis is complex
        if analysis_matches >= 2 and word_count > 20:
            return TaskComplexity.COMPLEX

        # Long creative tasks are expert level
        if creative_matches >= 1 and word_count > 30:
            return TaskComplexity.EXPERT

        # Medium length with some patterns
        if word_count > 20:
            return TaskComplexity.MODERATE

        # Short with patterns
        if code_matches > 0 or math_matches > 0:
            return TaskComplexity.MODERATE

        return TaskComplexity.SIMPLE

    def _estimate_output_tokens(self, complexity: TaskComplexity, category: TaskCategory) -> int:
        """Estimate output token count"""

        base_tokens = {
            TaskComplexity.TRIVIAL: 20,
            TaskComplexity.SIMPLE: 100,
            TaskComplexity.MODERATE: 300,
            TaskComplexity.COMPLEX: 800,
            TaskComplexity.EXPERT: 1500,
        }

        # Category multipliers
        multipliers = {
            TaskCategory.GREETING: 0.5,
            TaskCategory.CODE: 1.5,
            TaskCategory.CREATIVE: 1.5,
            TaskCategory.ANALYSIS: 1.3,
            TaskCategory.MATH: 0.8,
        }

        base = base_tokens.get(complexity, 200)
        multiplier = multipliers.get(category, 1.0)

        return int(base * multiplier)
