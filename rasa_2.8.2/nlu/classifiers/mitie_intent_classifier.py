import os
import typing
from typing import Any, Dict, List, Optional, Text, Type

from rasa.nlu.utils.mitie_utils import MitieNLP
from rasa.nlu.tokenizers.tokenizer import Tokenizer
from rasa.nlu.classifiers.classifier import IntentClassifier
from rasa.nlu.components import Component
from rasa.nlu.config import RasaNLUModelConfig
from rasa.nlu.model import Metadata
from rasa.nlu.constants import TOKENS_NAMES
from rasa.shared.nlu.constants import TEXT, INTENT
from rasa.shared.nlu.training_data.training_data import TrainingData
from rasa.shared.nlu.training_data.message import Message

if typing.TYPE_CHECKING:
    import mitie


class MitieIntentClassifier(IntentClassifier):
    @classmethod
    def required_components(cls) -> List[Type[Component]]:
        return [MitieNLP, Tokenizer]

    def __init__(
        self,
        component_config: Optional[Dict[Text, Any]] = None,
        clf: Optional["mitie.text_categorizer"] = None,
    ) -> None:
        """Construct a new intent classifier using the MITIE framework."""
        super().__init__(component_config)
        self.clf = clf

    @classmethod
    def required_packages(cls) -> List[Text]:
        return ["mitie"]

    def train(
        self,
        training_data: TrainingData,
        config: Optional[RasaNLUModelConfig] = None,
        **kwargs: Any,
    ) -> None:
        import mitie

        model_file = kwargs.get("mitie_file")
        if not model_file:
            raise Exception(
                "Can not run MITIE entity extractor without a "
                "language model. Make sure this component is "
                "preceeded by the 'MitieNLP' component."
            )

        trainer = mitie.text_categorizer_trainer(model_file)
        trainer.num_threads = kwargs.get("num_threads", 1)

        for example in training_data.intent_examples:
            tokens = self._tokens_of_message(example)
            trainer.add_labeled_text(tokens, example.get(INTENT))

        if training_data.intent_examples:
            # we can not call train if there are no examples!
            self.clf = trainer.train()

    def process(self, message: Message, **kwargs: Any) -> None:

        mitie_feature_extractor = kwargs.get("mitie_feature_extractor")
        if not mitie_feature_extractor:
            raise Exception(
                "Failed to train 'MitieFeaturizer'. "
                "Missing a proper MITIE feature extractor."
            )

        if self.clf:
            token_strs = self._tokens_of_message(message)
            intent, confidence = self.clf(token_strs, mitie_feature_extractor)
        else:
            # either the model didn't get trained or it wasn't
            # provided with any data
            intent = None
            confidence = 0.0

        message.set(
            "intent", {"name": intent, "confidence": confidence}, add_to_output=True
        )

    @staticmethod
    def _tokens_of_message(message: Message) -> List[Text]:
        return [token.text for token in message.get(TOKENS_NAMES[TEXT], [])]

    @classmethod
    def load(
        cls,
        meta: Dict[Text, Any],
        model_dir: Text,
        model_metadata: Optional[Metadata] = None,
        cached_component: Optional["MitieIntentClassifier"] = None,
        **kwargs: Any,
    ) -> "MitieIntentClassifier":
        """Loads trained component (see parent class for full docstring)."""
        import mitie

        file_name = meta.get("file")

        if not file_name:
            return cls(meta)
        classifier_file = os.path.join(model_dir, file_name)
        if os.path.exists(classifier_file):
            classifier = mitie.text_categorizer(classifier_file)
            return cls(meta, classifier)
        else:
            return cls(meta)

    def persist(self, file_name: Text, model_dir: Text) -> Dict[Text, Any]:

        if self.clf:
            file_name = file_name + ".dat"
            classifier_file = os.path.join(model_dir, file_name)
            self.clf.save_to_disk(classifier_file, pure_model=True)
            return {"file": file_name}
        else:
            return {"file": None}
