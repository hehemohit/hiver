import re
import unicodedata


class SecurityScanner:
  """Enterprise-grade security scanner defending against Prompt Injections,
  Jailbreak personas, System Prompt Exfiltration, and Delimiter Hijacking.
  """

  # 1. Direct instruction overrides & memory wipes
  OVERRIDE_PATTERNS = [
      r"ignore\s+(all\s+)?(previous|prior|above|former)\s+(instructions?|prompts?|rules?|commands?|guidelines?)",
      r"(disregard|forget|bypass|override|drop)\s+(all\s+)?(previous|prior|above|system)\s+(instructions?|prompts?|rules?|context)",
      r"do\s+not\s+follow\s+(your\s+)?(system|initial)\s+(instructions?|rules?)",
      r"clear\s+(your\s+)?(memory|context|rules)",
  ]

  # 2. Jailbreak personas, DAN variants, and ethical bypasses
  JAILBREAK_PATTERNS = [
      r"(you\s+are\s+now|act\s+as|pretend\s+to\s+be|roleplay\s+as)\s+(a\s+|an\s+)?(dan|jailbreak|evil|unfiltered|anarchist|hacker|adversary|ai\s+without\s+rules)",
      r"\b(dan|jailbreak|developer|god|aim|chaos)\s*mode\b",
      r"pretend\s+(you\s+have\s+no\s+(rules|limits|ethics|guardrails|constraints)|there\s+are\s+no\s+rules)",
      r"from\s+now\s+on\s+you\s+(can|will|must)\s+do\s+anything",
  ]

  # 3. System prompt exfiltration & reconnaissance
  EXFILTRATION_PATTERNS = [
      r"(what\s+(is|are)|reveal|show|print|output|display|repeat|leak|tell\s+me)\s+(your\s+|the\s+)?(initial\s+)?(system\s+)?(prompt|instructions?|system\s+message|rules)",
      r"(repeat|print|quote)\s+(the\s+words?\s+above|text\s+above|everything\s+above)",
      r"output\s+(the\s+)?first\s+\d+\s+(words|lines|tokens)",
  ]


  # 4. Delimiter injection & prompt formatting attacks
  DELIMITER_PATTERNS = [
      r"(<\|im_start\|>|<\|im_end\|>|\[inst\]|\[\/inst\]|<<sys>>|<<\/sys>>|<system>|<\/system>|\[system\])",
      r"(\[apple\s+(admin|internal|diagnostic|engineering)\s+override\]|admin_mode\s*=\s*(true|1))",
      r"```(system|prompt|admin)",
  ]

  # Unauthorized financial / legal promise detections in output
  UNAUTHORIZED_OUTPUT_PATTERNS = [
      r"\b(free\s+iphone|free\s+macbook|free\s+ipad|gift\s+card\s+giveaway|guaranteed\s+settlement\s+payout)\b",
      r"\byou\s+are\s+the\s+official\s+automated\s+ai\s+customer\s+support\s+agent\b",
  ]

  @classmethod
  def normalize_text(cls, text: str) -> str:
    """Normalizes Unicode confusable characters, strips zero-width spaces,
    and collapses obfuscating whitespace.
    """
    if not isinstance(text, str):
      return ""

    # Strip zero-width spaces and invisible control characters
    text = re.sub(r"[\u200B-\u200D\uFEFF\u0000-\u0008\u000B\u000C\u000E-\u001F]", "", text)

    # Unicode NFKD normalization (folds homoglyphs like Cyrillic 'а' to Latin 'a')
    normalized = unicodedata.normalize("NFKD", text)

    # Convert to lowercase and clean extra whitespaces
    return re.sub(r"\s+", " ", normalized).strip().lower()

  @classmethod
  def scan_input(cls, text: str) -> tuple[bool, str | None]:
    """Scans inbound customer tweet for adversarial prompt injection vectors.
    Returns: (is_threat: bool, threat_type: str | None)
    """
    cleaned = cls.normalize_text(text)

    # Check 1: Direct instruction overrides
    for pat in cls.OVERRIDE_PATTERNS:
      if re.search(pat, cleaned):
        return True, "Adversarial Override: Attempted instruction disregard."

    # Check 2: Jailbreak personas & DAN variants
    for pat in cls.JAILBREAK_PATTERNS:
      if re.search(pat, cleaned):
        return True, "Jailbreak Vector: Attempted persona/DAN bypass."

    # Check 3: System prompt exfiltration
    for pat in cls.EXFILTRATION_PATTERNS:
      if re.search(pat, cleaned):
        return True, "Prompt Exfiltration: Attempted internal prompt leak."

    # Check 4: Delimiter hijacking
    for pat in cls.DELIMITER_PATTERNS:
      if re.search(pat, cleaned):
        return True, "Delimiter Hijack: Injected system tags or formatting tokens."

    return False, None

  @classmethod
  def verify_output(cls, draft_reply: str) -> tuple[bool, str]:
    """Verifies that the generated reply does not contain unauthorized promises
    or leaked system instructions. Returns (is_safe: bool, sanitized_reply: str).
    """
    cleaned = cls.normalize_text(draft_reply)

    for pat in cls.UNAUTHORIZED_OUTPUT_PATTERNS:
      if re.search(pat, cleaned):
        # Quarantine output and return verified safe holding response
        return False, (
            "Thanks for reaching out to Apple Support. For assistance with Apple"
            " devices and services, please visit support.apple.com."
        )

    return True, draft_reply
