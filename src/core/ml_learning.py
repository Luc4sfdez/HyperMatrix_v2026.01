"""
HyperMatrix v2026 - ML Learning System
Learns from user decisions to improve future recommendations.
"""

import json
import logging
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set, Optional, Any, Tuple
from collections import defaultdict
import pickle

logger = logging.getLogger(__name__)


@dataclass
class Decision:
    """A user decision about code consolidation."""
    id: str
    timestamp: str
    decision_type: str  # 'merge', 'keep_separate', 'delete', 'rename', 'select_master'
    context: Dict[str, Any]  # Features of the decision context
    choice: str  # What the user chose
    files_involved: List[str]
    similarity_scores: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Recommendation:
    """A recommendation based on learned patterns."""
    action: str
    confidence: float
    reasoning: List[str]
    similar_decisions: int
    features_matched: Dict[str, Any]


@dataclass
class LearningStats:
    """Statistics about the learning system."""
    total_decisions: int
    decisions_by_type: Dict[str, int]
    accuracy_estimate: float
    most_common_patterns: List[Dict]
    last_updated: str


class FeatureExtractor:
    """Extracts features from code/files for learning."""

    @staticmethod
    def extract_file_features(filepath: str) -> Dict[str, Any]:
        """Extract features from a file for learning."""
        path = Path(filepath)
        features = {
            'filename': path.name,
            'extension': path.suffix,
            'path_depth': len(path.parts),
            'in_test_dir': 'test' in str(path).lower(),
            'in_src_dir': 'src' in str(path).lower(),
            'is_init': path.name == '__init__.py',
        }

        if path.exists():
            try:
                content = path.read_text(encoding='utf-8', errors='ignore')
                features.update({
                    'line_count': content.count('\n') + 1,
                    'char_count': len(content),
                    'has_docstring': '"""' in content or "'''" in content,
                    'has_tests': 'def test_' in content or 'class Test' in content,
                    'import_count': content.count('import '),
                    'class_count': content.count('class '),
                    'function_count': content.count('def '),
                })
            except Exception:
                pass

        return features

    @staticmethod
    def extract_comparison_features(
        files: List[str],
        similarity_scores: Dict[str, float]
    ) -> Dict[str, Any]:
        """Extract features from a file comparison context."""
        features = {
            'file_count': len(files),
            'avg_similarity': sum(similarity_scores.values()) / len(similarity_scores) if similarity_scores else 0,
            'max_similarity': max(similarity_scores.values()) if similarity_scores else 0,
            'min_similarity': min(similarity_scores.values()) if similarity_scores else 0,
            'same_names': len(set(Path(f).name for f in files)) == 1,
        }

        # Check if files are in same directory structure
        parents = [str(Path(f).parent) for f in files]
        features['same_parent'] = len(set(parents)) == 1
        features['common_parent_depth'] = len(set.intersection(*[
            set(Path(p).parts) for p in parents
        ])) if parents else 0

        return features


class PatternMatcher:
    """Matches patterns in decisions to make recommendations."""

    def __init__(self):
        self.patterns: Dict[str, List[Dict]] = defaultdict(list)

    def add_pattern(self, decision_type: str, features: Dict, choice: str):
        """Add a pattern from a decision."""
        self.patterns[decision_type].append({
            'features': features,
            'choice': choice,
        })

    def find_matching_patterns(
        self,
        decision_type: str,
        features: Dict,
        threshold: float = 0.7
    ) -> List[Tuple[Dict, float]]:
        """Find patterns matching the given features."""
        matches = []

        for pattern in self.patterns.get(decision_type, []):
            similarity = self._calculate_feature_similarity(
                features, pattern['features']
            )
            if similarity >= threshold:
                matches.append((pattern, similarity))

        return sorted(matches, key=lambda x: x[1], reverse=True)

    def _calculate_feature_similarity(
        self,
        features1: Dict,
        features2: Dict
    ) -> float:
        """Calculate similarity between two feature sets."""
        common_keys = set(features1.keys()) & set(features2.keys())
        if not common_keys:
            return 0.0

        matches = 0
        for key in common_keys:
            v1 = features1[key]
            v2 = features2[key]

            if isinstance(v1, bool) and isinstance(v2, bool):
                if v1 == v2:
                    matches += 1
            elif isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                # Numeric similarity
                max_val = max(abs(v1), abs(v2), 1)
                if abs(v1 - v2) / max_val < 0.2:
                    matches += 1
            elif v1 == v2:
                matches += 1

        return matches / len(common_keys)


class MLLearningSystem:
    """
    Machine Learning system that learns from user decisions.

    Features:
    - Records all user decisions about code consolidation
    - Extracts features from decision contexts
    - Finds patterns in decisions
    - Provides recommendations based on past decisions
    - Improves over time with more data
    """

    def __init__(self, storage_path: str = "hypermatrix_learning.json"):
        self.storage_path = Path(storage_path)
        self.decisions: List[Decision] = []
        self.feature_extractor = FeatureExtractor()
        self.pattern_matcher = PatternMatcher()
        self._load_data()

    def record_decision(
        self,
        decision_type: str,
        files: List[str],
        choice: str,
        similarity_scores: Dict[str, float] = None,
        metadata: Dict[str, Any] = None
    ) -> Decision:
        """
        Record a user decision for learning.

        Args:
            decision_type: Type of decision (merge, keep_separate, delete, etc.)
            files: Files involved in the decision
            choice: What the user chose
            similarity_scores: Similarity scores between files
            metadata: Additional context

        Returns:
            The recorded Decision
        """
        # Generate unique ID
        decision_id = hashlib.md5(
            f"{datetime.utcnow().isoformat()}{files}{choice}".encode()
        ).hexdigest()[:12]

        # Extract context features
        file_features = [
            self.feature_extractor.extract_file_features(f)
            for f in files
        ]

        comparison_features = self.feature_extractor.extract_comparison_features(
            files, similarity_scores or {}
        )

        context = {
            'file_features': file_features,
            'comparison_features': comparison_features,
        }

        decision = Decision(
            id=decision_id,
            timestamp=datetime.utcnow().isoformat(),
            decision_type=decision_type,
            context=context,
            choice=choice,
            files_involved=files,
            similarity_scores=similarity_scores or {},
            metadata=metadata or {},
        )

        self.decisions.append(decision)

        # Add to pattern matcher
        self.pattern_matcher.add_pattern(
            decision_type,
            comparison_features,
            choice
        )

        # Save periodically
        if len(self.decisions) % 10 == 0:
            self._save_data()

        logger.info(f"Recorded decision: {decision_type} -> {choice}")
        return decision

    def get_recommendation(
        self,
        decision_type: str,
        files: List[str],
        similarity_scores: Dict[str, float] = None
    ) -> Optional[Recommendation]:
        """
        Get a recommendation based on past decisions.

        Args:
            decision_type: Type of decision needed
            files: Files involved
            similarity_scores: Current similarity scores

        Returns:
            Recommendation if sufficient data, None otherwise
        """
        if len(self.decisions) < 5:
            return None  # Not enough data to recommend

        # Extract features
        comparison_features = self.feature_extractor.extract_comparison_features(
            files, similarity_scores or {}
        )

        # Find matching patterns
        matches = self.pattern_matcher.find_matching_patterns(
            decision_type, comparison_features
        )

        if not matches:
            return None

        # Count choices
        choice_counts: Dict[str, int] = defaultdict(int)
        total_weight = 0

        for pattern, similarity in matches[:10]:  # Top 10 matches
            choice_counts[pattern['choice']] += similarity
            total_weight += similarity

        if not choice_counts:
            return None

        # Find best choice
        best_choice = max(choice_counts.items(), key=lambda x: x[1])
        confidence = best_choice[1] / total_weight if total_weight > 0 else 0

        # Generate reasoning
        reasoning = self._generate_reasoning(
            decision_type, comparison_features, matches, best_choice[0]
        )

        return Recommendation(
            action=best_choice[0],
            confidence=confidence,
            reasoning=reasoning,
            similar_decisions=len(matches),
            features_matched=comparison_features,
        )

    def get_recommendations_batch(
        self,
        items: List[Dict[str, Any]]
    ) -> List[Optional[Recommendation]]:
        """Get recommendations for multiple items."""
        return [
            self.get_recommendation(
                item['decision_type'],
                item['files'],
                item.get('similarity_scores')
            )
            for item in items
        ]

    def get_stats(self) -> LearningStats:
        """Get statistics about the learning system."""
        decisions_by_type: Dict[str, int] = defaultdict(int)
        for d in self.decisions:
            decisions_by_type[d.decision_type] += 1

        # Calculate accuracy estimate (based on pattern consistency)
        accuracy = self._estimate_accuracy()

        # Find most common patterns
        common_patterns = self._find_common_patterns()

        return LearningStats(
            total_decisions=len(self.decisions),
            decisions_by_type=dict(decisions_by_type),
            accuracy_estimate=accuracy,
            most_common_patterns=common_patterns,
            last_updated=datetime.utcnow().isoformat(),
        )

    def export_data(self, filepath: str) -> bool:
        """Export all learning data."""
        try:
            data = {
                'decisions': [asdict(d) for d in self.decisions],
                'exported_at': datetime.utcnow().isoformat(),
            }
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return False

    def import_data(self, filepath: str) -> int:
        """Import learning data from file."""
        try:
            with open(filepath) as f:
                data = json.load(f)

            imported = 0
            for d in data.get('decisions', []):
                decision = Decision(**d)
                if decision.id not in {d.id for d in self.decisions}:
                    self.decisions.append(decision)
                    imported += 1

            self._save_data()
            return imported
        except Exception as e:
            logger.error(f"Import failed: {e}")
            return 0

    def clear_data(self) -> bool:
        """Clear all learning data."""
        self.decisions = []
        self.pattern_matcher = PatternMatcher()
        return self._save_data()

    def _generate_reasoning(
        self,
        decision_type: str,
        features: Dict,
        matches: List[Tuple[Dict, float]],
        recommended_choice: str
    ) -> List[str]:
        """Generate human-readable reasoning for recommendation."""
        reasoning = []

        reasoning.append(
            f"Based on {len(matches)} similar past decisions for '{decision_type}'"
        )

        if features.get('same_names'):
            reasoning.append("Files have the same name")

        if features.get('avg_similarity', 0) > 0.8:
            reasoning.append(
                f"High average similarity ({features['avg_similarity']:.0%})"
            )

        if features.get('same_parent'):
            reasoning.append("Files are in the same directory")

        # Count how many times this choice was made
        choice_count = sum(
            1 for m, _ in matches if m['choice'] == recommended_choice
        )
        reasoning.append(
            f"'{recommended_choice}' was chosen in {choice_count}/{len(matches)} "
            f"similar situations"
        )

        return reasoning

    def _estimate_accuracy(self) -> float:
        """Estimate accuracy based on pattern consistency."""
        if len(self.decisions) < 10:
            return 0.0

        # Check how consistent choices are for similar situations
        consistencies = []

        for decision in self.decisions[-50:]:  # Check recent decisions
            features = decision.context.get('comparison_features', {})
            matches = self.pattern_matcher.find_matching_patterns(
                decision.decision_type, features, threshold=0.8
            )

            if len(matches) >= 3:
                # Count how many matched the same choice
                same_choice = sum(
                    1 for m, _ in matches if m['choice'] == decision.choice
                )
                consistencies.append(same_choice / len(matches))

        return sum(consistencies) / len(consistencies) if consistencies else 0.0

    def _find_common_patterns(self) -> List[Dict]:
        """Find the most common decision patterns."""
        patterns: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for decision in self.decisions:
            key = decision.decision_type
            patterns[key][decision.choice] += 1

        result = []
        for decision_type, choices in patterns.items():
            total = sum(choices.values())
            for choice, count in sorted(choices.items(), key=lambda x: -x[1])[:3]:
                result.append({
                    'decision_type': decision_type,
                    'choice': choice,
                    'count': count,
                    'percentage': count / total if total else 0,
                })

        return sorted(result, key=lambda x: x['count'], reverse=True)[:10]

    def _save_data(self) -> bool:
        """Save learning data to file."""
        try:
            data = {
                'decisions': [asdict(d) for d in self.decisions],
                'saved_at': datetime.utcnow().isoformat(),
            }
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save learning data: {e}")
            return False

    def _load_data(self):
        """Load learning data from file."""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            for d in data.get('decisions', []):
                decision = Decision(**d)
                self.decisions.append(decision)

                # Rebuild pattern matcher
                comparison_features = decision.context.get('comparison_features', {})
                self.pattern_matcher.add_pattern(
                    decision.decision_type,
                    comparison_features,
                    decision.choice
                )

            logger.info(f"Loaded {len(self.decisions)} decisions from storage")
        except Exception as e:
            logger.error(f"Failed to load learning data: {e}")


# Singleton instance
_learning_system: Optional[MLLearningSystem] = None


def get_learning_system(storage_path: str = "hypermatrix_learning.json") -> MLLearningSystem:
    """Get or create the global learning system instance."""
    global _learning_system
    if _learning_system is None:
        _learning_system = MLLearningSystem(storage_path)
    return _learning_system
