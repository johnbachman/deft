import os
import uuid
import json
import numpy as np
from collections import Counter
from nose.plugins.attrib import attr
from sklearn.metrics import f1_score

from adeft.locations import TEST_RESOURCES_PATH
from adeft.modeling.classify import AdeftClassifier, load_model


# Get test model path so we can write a temporary file here
TEST_MODEL_PATH = os.path.join(TEST_RESOURCES_PATH, 'test_model')
# Path to scratch directory to write files to during tests
SCRATCH_PATH = os.path.join(TEST_RESOURCES_PATH, 'scratch')


with open(os.path.join(TEST_RESOURCES_PATH,
                       'example_training_data.json'), 'r') as f:
    data = json.load(f)


# The classifier works slightly differently for multiclass than it does for
# binary labels. Both cases must be tested separately.
@attr('slow')
def test_train():
    params = {'C': 1.0,
              'ngram_range': (1, 2),
              'max_features': 1000}
    classifier = AdeftClassifier('IR', ['HGNC:6091', 'MESH:D011839'])
    texts = data['texts']
    labels = data['labels']
    classifier.train(texts, labels, **params)
    assert hasattr(classifier, 'estimator')
    assert (f1_score(labels, classifier.predict(texts),
                     labels=['HGNC:6091', 'MESH:D011839'],
                     average='weighted') > 0.5)


@attr('slow')
def test_cv_multiclass():
    params = {'C': [1.0],
              'max_features': [1000]}
    classifier = AdeftClassifier('IR', ['HGNC:6091', 'MESH:D011839'])
    texts = data['texts']
    labels = data['labels']
    classifier.cv(texts, labels, param_grid=params, cv=2)
    assert classifier.best_score > 0.5
    assert classifier.stats['label_distribution'] == dict(Counter(labels))
    assert classifier.stats['precision']['mean'] > 0.5


@attr('slow')
def test_cv_binary():
    params = {'C': [1.0],
              'max_features': [1000]}
    texts = data['texts']
    labels = [label if label == 'HGNC:6091' else 'ungrounded'
              for label in data['labels']]
    classifier = AdeftClassifier('IR', ['HGNC:6091'])
    classifier.cv(texts, labels, param_grid=params, cv=2)
    assert classifier.best_score > 0.5
    assert classifier.stats['label_distribution'] == dict(Counter(labels))
    assert classifier.stats['precision']['mean'] > 0.5


@attr('slow')
def test_feature_importance_multiclass():
    params = {'C': 1.0,
              'ngram_range': (1, 2),
              'max_features': 1000}
    classifier = AdeftClassifier('IR', ['HGNC:6091', 'MESH:D011839'])
    texts = data['texts']
    labels = data['labels']
    classifier.train(texts, labels, **params)
    feature_importances = classifier.feature_importances()
    assert isinstance(feature_importances, dict)
    assert set(feature_importances.keys()) == set(labels)
    for label, importances in feature_importances.items():
        # check that importances are sorted
        assert importances == sorted(importances, key=lambda x: -x[1])
        # check that output is of the correct type
        assert all(isinstance(x, tuple) and
                   len(x) == 2 and
                   isinstance(x[0], str) and
                   isinstance(x[1], float)
                   for x in importances)
    # check if selected important features have positive score
    assert all([score > 0 for feature, score
                in feature_importances['HGNC:6091']
                if feature in ['irs1', 'igf1r', 'signaling']])
    assert all([score > 0 for feature, score
                in feature_importances['MESH:D011839']
                if feature in ['radiation', 'exposure', 'dna']])


@attr('slow')
def test_feature_importance_binary():
    params = {'C': 1.0,
              'ngram_range': (1, 2),
              'max_features': 1000}
    classifier = AdeftClassifier('IR', ['HGNC:6091'])
    texts = data['texts']
    labels = [label if label == 'HGNC:6091' else 'ungrounded'
              for label in data['labels']]
    classifier.train(texts, labels, **params)
    feature_importances = classifier.feature_importances()
    assert isinstance(feature_importances, dict)
    assert set(feature_importances.keys()) == set(labels)
    for label, importances in feature_importances.items():
        # check that importances are sorted
        assert importances == sorted(importances, key=lambda x: -x[1])
        # check that output is of the correct type
        assert all(isinstance(x, tuple) and
                   len(x) == 2 and
                   isinstance(x[0], str) and
                   isinstance(x[1], float)
                   for x in importances)
    # check if selected important features have positive score
    assert all([score > 0 for feature, score
                in feature_importances['HGNC:6091']
                if feature in ['irs1', 'igf1r', 'phosphorylation']])


def test_serialize():
    """Test that models can correctly be saved to and loaded from gzipped json
    """
    texts = data['texts']
    classifier1 = load_model(os.path.join(TEST_MODEL_PATH, 'IR',
                                          'IR_model.gz'))
    temp_filename = os.path.join(SCRATCH_PATH, uuid.uuid4().hex)
    classifier1.dump_model(temp_filename)

    classifier2 = load_model(temp_filename)
    classifier2.dump_model(temp_filename)

    classifier3 = load_model(temp_filename)

    preds1, preds2, preds3 = (classifier1.predict_proba(texts),
                              classifier2.predict_proba(texts),
                              classifier3.predict_proba(texts))
    # Check that generated predictions are the same
    assert np.array_equal(preds1, preds2)
    assert np.array_equal(preds2, preds3)
    # Check that model stats are the same
    assert classifier1.stats == classifier2.stats == classifier3.stats
    # Check that the calculated feature importance scores are the same
    assert classifier1.feature_importances() == \
        classifier2.feature_importances() == \
        classifier3.feature_importances()
    os.remove(temp_filename)
