"""Clustering support (Milestone 11): feature-table assembly and the
stability primitives the notebook reuses once per leave-one-study-out /
bootstrap run. The clustering algorithms themselves (KMeans,
AgglomerativeClustering, GaussianMixture) are called directly from
scikit-learn in the notebook -- thin one-line wrappers here would add
nothing testable.
"""
