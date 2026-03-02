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
    SECURITY = "security"
    IMAGE_GEN = "image_gen"
    AUDIO_GEN = "audio_gen"
    VIDEO_GEN = "video_gen"
    MUSIC_GEN = "music_gen"
    DOCUMENT_GEN = "document_gen"
    RESEARCH = "research"


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

    # Security / offensive / defensive patterns
    SECURITY_PATTERNS = [
        r"\b(exploit|payload|bypass|nmap|shellcode|pentest|pentesting)\b",
        r"\b(red\s*team|blue\s*team|attack\s*chain|lateral\s*movement)\b",
        r"\b(cve|vulnerability|vuln|privilege\s*escalation|priv\s*esc)\b",
        r"\b(reverse\s*shell|bind\s*shell|meterpreter|cobalt\s*strike)\b",
        r"\b(active\s*directory|ad\s*attack|kerberoast|mimikatz|bloodhound)\b",
        r"\b(malware|ransomware|rootkit|backdoor|c2|command\s*and\s*control)\b",
        r"\b(osint|reconnaissance|recon|enumeration|footprint)\b",
        r"\b(buffer\s*overflow|heap\s*spray|rop\s*chain|format\s*string)\b",
        r"\b(waf\s*bypass|edr\s*bypass|amsi\s*bypass|etw\s*patch)\b",
    ]

    # Image generation patterns
    IMAGE_PATTERNS = [
        r"\b(draw|sketch|illustrate|paint|render)\b",
        r"\b(generate\s+(an?\s+)?image|create\s+(an?\s+)?image)\b",
        r"\b(flux|stable\s*diffusion|lora|img2img|txt2img)\b",
        r"\b(portrait|landscape|concept\s*art|illustration)\b",
    ]

    # Audio generation patterns (TTS / voice)
    AUDIO_PATTERNS = [
        r"\b(tts|text\s*to\s*speech|voice\s*clone|voice\s*synthesis)\b",
        r"\b(cosyvoice|fish\s*speech|bark|tortoise)\b",
        r"\b(speak\s+this|read\s+aloud|narrate)\b",
    ]

    # Video generation patterns
    VIDEO_PATTERNS = [
        r"\b(create\s+video|generate\s+video|make\s+video|video\s+generation)\b",
        r"\b(animate|video\s+clip|render\s+video)\b",
        r"\b(cogvideox|mochi|wan2\.1|video\s+model)\b",
    ]

    # Music generation patterns (distinct from TTS)
    MUSIC_PATTERNS = [
        r"\b(compose\s+music|create\s+music|generate\s+music|generate\s+song)\b",
        r"\b(make\s+soundtrack|create\s+beat|music\s+gen)\b",
        r"\b(audiocraft|musicgen|stable\s*audio|music\s+generation)\b",
        r"\b(sound\s+effect|ambient\s+music|background\s+music)\b",
    ]

    # Document generation patterns
    DOCUMENT_PATTERNS = [
        r"\b(write\s+doc|create\s+document|create\s+word|make\s+word)\b",
        r"\b(create\s+presentation|make\s+presentation|create\s+powerpoint|make\s+slides)\b",
        r"\b(create\s+spreadsheet|make\s+spreadsheet|create\s+excel)\b",
        r"\b(generate\s+report|write\s+report)\b",
    ]

    # Research patterns
    RESEARCH_PATTERNS = [
        r"\b(deep\s+research|deep\s+dive|comprehensive\s+analysis)\b",
        r"\b(find\s+information\s+about|investigate\s+thoroughly)\b",
        r"\b(research\s+topic|in-depth\s+study)\b",
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
        self._security_re = [re.compile(p, re.IGNORECASE) for p in self.SECURITY_PATTERNS]
        self._image_re = [re.compile(p, re.IGNORECASE) for p in self.IMAGE_PATTERNS]
        self._audio_re = [re.compile(p, re.IGNORECASE) for p in self.AUDIO_PATTERNS]
        self._video_re = [re.compile(p, re.IGNORECASE) for p in self.VIDEO_PATTERNS]
        self._music_re = [re.compile(p, re.IGNORECASE) for p in self.MUSIC_PATTERNS]
        self._document_re = [re.compile(p, re.IGNORECASE) for p in self.DOCUMENT_PATTERNS]
        self._research_re = [re.compile(p, re.IGNORECASE) for p in self.RESEARCH_PATTERNS]

    def _match_all_patterns(self, query: str) -> dict[str, int]:
        """Return match counts for each pattern group against query."""
        return {
            "code": sum(1 for p in self._code_re if p.search(query)),
            "math": sum(1 for p in self._math_re if p.search(query)),
            "analysis": sum(1 for p in self._analysis_re if p.search(query)),
            "creative": sum(1 for p in self._creative_re if p.search(query)),
            "tool": sum(1 for p in self._tool_re if p.search(query)),
            "security": sum(1 for p in self._security_re if p.search(query)),
            "image": sum(1 for p in self._image_re if p.search(query)),
            "audio": sum(1 for p in self._audio_re if p.search(query)),
            "video": sum(1 for p in self._video_re if p.search(query)),
            "music": sum(1 for p in self._music_re if p.search(query)),
            "document": sum(1 for p in self._document_re if p.search(query)),
            "research": sum(1 for p in self._research_re if p.search(query)),
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
        if counts.get("security", 0) >= 1:
            return TaskCategory.SECURITY
        if counts.get("video", 0) >= 1:
            return TaskCategory.VIDEO_GEN
        if counts.get("music", 0) >= 1:
            return TaskCategory.MUSIC_GEN
        if counts.get("document", 0) >= 1:
            return TaskCategory.DOCUMENT_GEN
        if counts.get("image", 0) >= 1:
            return TaskCategory.IMAGE_GEN
        if counts.get("audio", 0) >= 1:
            return TaskCategory.AUDIO_GEN
        if counts.get("research", 0) >= 1:
            return TaskCategory.RESEARCH
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
            TaskCategory.SECURITY: 1.4,
            TaskCategory.IMAGE_GEN: 0.6,
            TaskCategory.AUDIO_GEN: 0.6,
            TaskCategory.VIDEO_GEN: 0.6,
            TaskCategory.MUSIC_GEN: 0.6,
            TaskCategory.DOCUMENT_GEN: 1.3,
            TaskCategory.RESEARCH: 1.5,
        }

        base = base_tokens.get(complexity, 200)
        multiplier = multipliers.get(category, 1.0)

        return int(base * multiplier)
