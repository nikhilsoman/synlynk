# Project Work Management Data Model

This model supports a general project-work application where people belong to
projects, projects contain tasks, and tasks can be assigned to multiple people.
It is intentionally normalized enough for an intermediate implementation while
remaining small enough to extend.

## Tables

### `projects`

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `project_id` | UUID | PK | Stable project identifier |
| `name` | VARCHAR(120) | NOT NULL | Display name |
| `description` | TEXT | NULL | Optional project context |
| `status` | VARCHAR(20) | NOT NULL, CHECK | `planned`, `active`, or `archived` |
| `created_at` | TIMESTAMP | NOT NULL | Creation time |

### `members`

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `member_id` | UUID | PK | Stable person identifier |
| `email` | VARCHAR(255) | NOT NULL, UNIQUE | Login/contact identity |
| `display_name` | VARCHAR(120) | NOT NULL | Name shown in the UI |
| `created_at` | TIMESTAMP | NOT NULL | Account creation time |

### `project_members`

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `project_id` | UUID | PK/FK → `projects.project_id` | Project side of membership |
| `member_id` | UUID | PK/FK → `members.member_id` | Member side of membership |
| `role` | VARCHAR(20) | NOT NULL, CHECK | `owner`, `editor`, or `viewer` |
| `joined_at` | TIMESTAMP | NOT NULL | When membership began |

The composite primary key prevents duplicate memberships. This table resolves
the many-to-many relationship between projects and members.

### `tasks`

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `task_id` | UUID | PK | Stable task identifier |
| `project_id` | UUID | NOT NULL, FK → `projects.project_id` | Owning project |
| `title` | VARCHAR(200) | NOT NULL | Short task summary |
| `details` | TEXT | NULL | Longer description |
| `status` | VARCHAR(20) | NOT NULL, CHECK | `todo`, `in_progress`, or `done` |
| `due_at` | TIMESTAMP | NULL | Optional deadline |
| `created_by` | UUID | NOT NULL, FK → `members.member_id` | Author |
| `created_at` | TIMESTAMP | NOT NULL | Creation time |

### `task_assignments`

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `task_id` | UUID | PK/FK → `tasks.task_id` | Task side of assignment |
| `member_id` | UUID | PK/FK → `members.member_id` | Assignee side |
| `assigned_at` | TIMESTAMP | NOT NULL | Assignment time |

This table resolves the many-to-many relationship between tasks and members.
The application should additionally verify that an assignee belongs to the
task's project before inserting an assignment.

## Relationships and invariants

```text
members 1 ───< project_members >─── 1 projects
projects 1 ───< tasks
members 1 ───< tasks                 (created_by)
members 1 ───< task_assignments >─── 1 tasks
```

- Deleting a project should cascade to `project_members`, `tasks`, and then
  `task_assignments`; deleting a member should be restricted while they own a
  project or authored a task.
- Index `tasks(project_id, status, due_at)` for project dashboards and
  `task_assignments(member_id)` for a member's workload view.
- Enforce the allowed status and role values with database `CHECK` constraints,
  and use application validation for the cross-table membership invariant.
