# Developer Documentation

## Release Checklist

0. Prerequsisite: The master branch contains the version to be
   released.
1. Update the version number with a PR to `master` (no review
   required).
2. Open and merge a PR `master` -> `pre-release` (no review
   required). This will built the docker images for the monitor and
   the reporting tool and push them to Docker Hub under
   `trustlines/tlbc-testnet-next:pre-release` and
   `trustlines/report-validator-next:pre-release`, respectively.
3. Test the monitor pre-release:
   - Pull the newly built image from Docker Hub.
   - Run the monitor connected to a synced node and check that it
     syncs and reports inactive validators (if any) by checking the
     log output and the created skip file.
   - Run the monitor in a pre-existing environment set up using the
     quickstart script and check that it continues staying in sync
     and reporting
   - Perform any additional tests compelled by the specifics of the
     update.
4. Open a PR `pre-release` -> `release`, wait for a review
   confirming that the necessary testing steps have been performed,
   and merge it.
5. Authorize the release in CircleCI
6. Check that the image is built and pushed to Docker Hub under
   `trustlines/tlbc-monitor:release` and
   `trustlines/report-validator:release`, respectively.
