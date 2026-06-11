# TODO

## Backlog

- [ ] Explore template details for self-hosted deployments.
  - Current behavior: the Explore template card details action opens the trial app flow and calls /console/api/trial-apps/{app_id}. Self-hosted deployments usually do not have local trial_apps data, so the details panel can return App not found even though Use template works.
  - Desired behavior: route the details action to a static template details modal backed by /console/api/explore/apps/{app_id}. Show template name, icon, mode, categories, description, disclaimer/copyright/privacy fields, and a create-from-template action for users with edit permission.
  - Keep the trial app preview only when enable_trial_app is enabled and the template has can_trial=true.
  - This is not a current priority; revisit when polishing the Explore experience for normal users and self-hosted administrators.
