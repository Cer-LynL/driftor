"""
Ticket analysis agent for classifying and understanding Jira issues.
"""
import re
from typing import Dict, List, Optional, Any
import structlog

from driftor.security.audit import audit, AuditEventType

logger = structlog.get_logger(__name__)


class TicketAnalyzer:
    """Agent for analyzing and classifying Jira tickets."""
    
    def __init__(self, db_session=None):
        self.db_session = db_session
        
        # Bug indicators and patterns
        self.bug_keywords = {
            'high_priority': [
                'crash', 'exception', 'error', 'null pointer', 'segfault', 'memory leak',
                'deadlock', 'hang', 'freeze', 'corrupt', 'fail', 'broken', 'not working'
            ],
            'medium_priority': [
                'bug', 'issue', 'problem', 'defect', 'wrong', 'incorrect', 'unexpected',
                'missing', 'invalid', 'timeout', 'slow', 'performance'
            ],
            'low_priority': [
                'typo', 'spelling', 'formatting', 'cosmetic', 'minor', 'ui', 'display'
            ]
        }
        
        # Component/technology indicators
        self.tech_indicators = {
            'frontend': ['ui', 'frontend', 'react', 'vue', 'angular', 'javascript', 'css', 'html'],
            'backend': ['api', 'backend', 'server', 'database', 'sql', 'rest', 'endpoint'],
            'mobile': ['android', 'ios', 'mobile', 'app', 'kotlin', 'swift'],
            'infrastructure': ['docker', 'kubernetes', 'aws', 'deployment', 'ci/cd', 'pipeline']
        }
        
        # Severity indicators
        self.severity_patterns = {
            'critical': [
                r'production\s+down', r'system\s+crash', r'data\s+loss', r'security\s+breach',
                r'cannot\s+login', r'payment\s+fail', r'critical\s+error'
            ],
            'high': [
                r'major\s+feature\s+broken', r'api\s+not\s+responding', r'database\s+error',
                r'user\s+cannot', r'application\s+crash'
            ],
            'medium': [
                r'incorrect\s+behavior', r'performance\s+issue', r'ui\s+bug',
                r'validation\s+error', r'timeout'
            ],
            'low': [
                r'minor\s+ui', r'cosmetic', r'typo', r'suggestion', r'enhancement'
            ]
        }
    
    async def classify_ticket(self, ticket_data: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
        """Classify and analyze a Jira ticket."""
        try:
            summary = ticket_data.get("summary", "").lower()
            description = ticket_data.get("description", "").lower()
            issue_type = ticket_data.get("issue_type", "").lower()
            priority = ticket_data.get("priority", "").lower()
            
            # Combine text for analysis
            full_text = f"{summary} {description}"
            
            # Basic classification
            classification = {
                "is_bug": self._is_bug_ticket(issue_type, full_text),
                "severity": self._analyze_severity(full_text, priority),
                "component": self._identify_component(full_text),
                "keywords": self._extract_keywords(full_text),
                "urgency_score": self._calculate_urgency_score(ticket_data),
                "complexity_estimate": self._estimate_complexity(full_text),
                "confidence": 0.0
            }
            
            # Calculate overall confidence
            classification["confidence"] = self._calculate_classification_confidence(
                classification, ticket_data
            )
            
            # Audit the classification
            await audit(
                event_type=AuditEventType.DATA_CREATED,
                tenant_id=tenant_id,
                resource_type="ticket_classification",
                resource_id=ticket_data.get("key", ""),
                details={
                    "is_bug": classification["is_bug"],
                    "severity": classification["severity"],
                    "confidence": classification["confidence"],
                    "urgency_score": classification["urgency_score"]
                }
            )
            
            logger.info(
                "Ticket classified",
                ticket_key=ticket_data.get("key"),
                is_bug=classification["is_bug"],
                severity=classification["severity"],
                confidence=classification["confidence"],
                tenant_id=tenant_id
            )
            
            return classification
            
        except Exception as e:
            logger.error(
                "Ticket classification failed",
                ticket_key=ticket_data.get("key", "unknown"),
                error=str(e),
                exc_info=True
            )
            
            # Return safe default
            return {
                "is_bug": False,
                "severity": "unknown",
                "component": "unknown",
                "keywords": [],
                "urgency_score": 0.0,
                "complexity_estimate": "medium",
                "confidence": 0.0,
                "error": str(e)
            }
    
    def _is_bug_ticket(self, issue_type: str, text: str) -> bool:
        """Determine if this is a bug ticket."""
        # Check issue type first
        bug_types = ['bug', 'defect', 'error', 'issue']
        if any(bug_type in issue_type for bug_type in bug_types):
            return True
        
        # Check content for bug indicators
        high_priority_count = sum(1 for keyword in self.bug_keywords['high_priority'] 
                                 if keyword in text)
        medium_priority_count = sum(1 for keyword in self.bug_keywords['medium_priority'] 
                                   if keyword in text)
        
        # Scoring logic
        bug_score = high_priority_count * 3 + medium_priority_count * 1
        
        return bug_score >= 2
    
    def _analyze_severity(self, text: str, priority: str) -> str:
        """Analyze severity based on text content and priority."""
        # Check for explicit severity patterns
        for severity, patterns in self.severity_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return severity
        
        # Check priority field
        priority_mapping = {
            'highest': 'critical',
            'high': 'high',
            'medium': 'medium',
            'low': 'low',
            'lowest': 'low'
        }
        
        if priority in priority_mapping:
            return priority_mapping[priority]
        
        # Default based on bug keywords
        high_count = sum(1 for keyword in self.bug_keywords['high_priority'] 
                        if keyword in text)
        if high_count >= 2:
            return 'high'
        elif high_count >= 1:
            return 'medium'
        else:
            return 'low'
    
    def _identify_component(self, text: str) -> str:
        """Identify the likely component/technology area."""
        component_scores = {}
        
        for component, keywords in self.tech_indicators.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                component_scores[component] = score
        
        if not component_scores:
            return 'unknown'
        
        # Return component with highest score
        return max(component_scores, key=component_scores.get)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract key technical terms and error indicators."""
        # Technical keywords to look for
        technical_terms = [
            'null pointer', 'exception', 'timeout', 'connection', 'database',
            'api', 'authentication', 'authorization', 'validation', 'parsing',
            'serialization', 'configuration', 'deployment', 'performance',
            'memory', 'cpu', 'network', 'ssl', 'certificate', 'cors'
        ]
        
        found_keywords = []
        for term in technical_terms:
            if term in text:
                found_keywords.append(term)
        
        # Also extract error codes and stack trace indicators
        error_patterns = [
            r'error\s+\d+', r'http\s+\d{3}', r'exception:\s+\w+',
            r'at\s+\w+\.\w+\(', r'line\s+\d+', r'column\s+\d+'
        ]
        
        for pattern in error_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            found_keywords.extend(matches)
        
        return list(set(found_keywords))  # Remove duplicates
    
    def _calculate_urgency_score(self, ticket_data: Dict[str, Any]) -> float:
        """Calculate urgency score based on various factors."""
        score = 0.0
        
        # Priority weight
        priority = ticket_data.get("priority", "").lower()
        priority_weights = {
            'highest': 1.0,
            'high': 0.8,
            'medium': 0.6,
            'low': 0.4,
            'lowest': 0.2
        }
        score += priority_weights.get(priority, 0.5)
        
        # Age factor (older tickets might be more urgent if unresolved)
        created = ticket_data.get("created")
        if created:
            # TODO: Calculate age and adjust score
            pass
        
        # Reporter/assignee factors
        assignee = ticket_data.get("assignee", {})
        if assignee:
            score += 0.2  # Assigned tickets are more urgent
        
        # Component criticality
        summary = ticket_data.get("summary", "").lower()
        description = ticket_data.get("description", "").lower()
        text = f"{summary} {description}"
        
        critical_components = ['payment', 'authentication', 'security', 'login', 'data']
        if any(comp in text for comp in critical_components):
            score += 0.3
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _estimate_complexity(self, text: str) -> str:
        """Estimate the complexity of fixing this issue."""
        complexity_indicators = {
            'high': [
                'architecture', 'refactor', 'migration', 'performance', 'scalability',
                'integration', 'third-party', 'legacy', 'database schema', 'security'
            ],
            'medium': [
                'api', 'validation', 'configuration', 'deployment', 'testing',
                'authentication', 'authorization', 'parsing', 'formatting'
            ],
            'low': [
                'typo', 'text', 'label', 'button', 'color', 'styling', 'css',
                'cosmetic', 'minor', 'tooltip', 'placeholder'
            ]
        }
        
        for complexity, indicators in complexity_indicators.items():
            if any(indicator in text for indicator in indicators):
                return complexity
        
        return 'medium'  # Default
    
    def _calculate_classification_confidence(
        self, 
        classification: Dict[str, Any], 
        ticket_data: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for the classification."""
        confidence = 0.0
        
        # Issue type confidence
        issue_type = ticket_data.get("issue_type", "").lower()
        if "bug" in issue_type or "defect" in issue_type:
            confidence += 0.4
        elif classification["is_bug"]:
            confidence += 0.2
        
        # Priority alignment
        priority = ticket_data.get("priority", "").lower()
        severity = classification["severity"]
        
        priority_severity_alignment = {
            ('highest', 'critical'): 0.3,
            ('high', 'high'): 0.3,
            ('medium', 'medium'): 0.2,
            ('low', 'low'): 0.2,
        }
        
        confidence += priority_severity_alignment.get((priority, severity), 0.1)
        
        # Keyword richness
        keyword_count = len(classification["keywords"])
        if keyword_count >= 3:
            confidence += 0.2
        elif keyword_count >= 1:
            confidence += 0.1
        
        # Component identification
        if classification["component"] != "unknown":
            confidence += 0.1
        
        return min(confidence, 1.0)  # Cap at 1.0
    
    def analyze_error_patterns(self, text: str) -> Dict[str, Any]:
        """Analyze specific error patterns in the ticket."""
        patterns = {
            'null_pointer': [
                r'null\s*pointer', r'nullpointerexception', r'cannot\s+read\s+property.*null',
                r'null\s+reference', r'object\s+reference\s+not\s+set'
            ],
            'timeout': [
                r'timeout', r'time\s*out', r'connection\s+timed\s+out', r'request\s+timeout'
            ],
            'authentication': [
                r'auth\w*\s+fail', r'login\s+fail', r'unauthorized', r'401\s+error',
                r'invalid\s+credentials', r'token\s+expired'
            ],
            'database': [
                r'database\s+error', r'sql\s+exception', r'connection\s+pool',
                r'deadlock', r'constraint\s+violation', r'duplicate\s+key'
            ],
            'api': [
                r'api\s+error', r'rest\s+error', r'http\s+\d{3}', r'endpoint\s+not\s+found',
                r'malformed\s+request', r'invalid\s+response'
            ],
            'memory': [
                r'memory\s+leak', r'out\s+of\s+memory', r'heap\s+space', r'stack\s+overflow',
                r'garbage\s+collect'
            ]
        }
        
        found_patterns = {}
        for pattern_type, pattern_list in patterns.items():
            matches = []
            for pattern in pattern_list:
                if re.search(pattern, text, re.IGNORECASE):
                    matches.append(pattern)
            
            if matches:
                found_patterns[pattern_type] = matches
        
        return found_patterns
    
    def extract_stack_trace_info(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract stack trace information if present."""
        # Look for common stack trace patterns
        stack_patterns = [
            r'at\s+[\w\.]+\([\w\.]+:\d+\)',  # Java stack trace
            r'File\s+"[^"]+",\s+line\s+\d+',  # Python stack trace
            r'in\s+[\w\.]+\s+at\s+line\s+\d+',  # PHP stack trace
            r'at\s+[\w\.]+\s+\([^)]+:\d+:\d+\)'  # JavaScript stack trace
        ]
        
        for pattern in stack_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                return {
                    "type": "stack_trace",
                    "lines": matches[:5],  # Limit to first 5 lines
                    "language": self._detect_language_from_stack_trace(matches[0])
                }
        
        return None
    
    def _detect_language_from_stack_trace(self, stack_line: str) -> str:
        """Detect programming language from stack trace format."""
        if 'at ' in stack_line and '.java:' in stack_line:
            return 'java'
        elif 'File "' in stack_line and 'line ' in stack_line:
            return 'python'
        elif ' in ' in stack_line and ' at line ' in stack_line:
            return 'php'
        elif '.js:' in stack_line or '.ts:' in stack_line:
            return 'javascript'
        else:
            return 'unknown'