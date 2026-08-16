# No configuration is needed here, and that is the point.
#
# pytest-bdd resolves a relative feature path against the directory of the module that
# calls scenarios(), unless bdd_features_base_dir is set in the ini file - in which case
# it resolves against pytest's rootdir instead, and rootdir depends on where pytest was
# invoked from. That setting is what made the suite behave differently from the repository
# root than from tools/l1_analyzer/. It has been removed from pyproject.toml, so
# step_defs/*.py reach features/*.feature by "../features/..." from any directory.
