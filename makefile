demo_d8graph:
	python setup.py build
	python demo_d8graph.py 


# This assumes you have done `rclone config` and created a setup
# called "alaska."  It doesn't matter which Google Account you use.
# The Drive folder is as shared by Gabe Wolken on 2022-04-27
fetch-sample-projects:
	rclone --drive-root-folder-id=1VHlnKiK8Ig2PTs23zTWCYVDqNjGMkEHL copy alaska:SampleProjects SampleProjects

fetch-se-alaska:
	rclone --drive-root-folder-id=1VHlnKiK8Ig2PTs23zTWCYVDqNjGMkEHL copy alaska:SE_Alaska SE_Alaska


