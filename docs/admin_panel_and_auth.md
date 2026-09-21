# Admin Panel & Authentication Documentation

This document records the architectural design, implementation details, API specifications, permission guards, and verification results for the **Admin Panel & Self-Service Account Management** features.

---

## 1. Initial Admin Account Setup

The designated main administrator account is initialized with the following credentials and capabilities:

- **Username**: `admin`
- **Email**: `esan3125@gmail.com`
- **Password**: `ish@npoudel888`
- **Privileges**:
  - `is_staff = True` (Django staff status)
  - `is_superuser = True` (Superuser status)
  - `profile.is_main_admin = True` (Permanent main admin flag in `apps.users.models.Profile`)

### Management Command
To initialize or refresh the main admin account at any time, execute:
```powershell
python backend/manage.py create_initial_admin
```
This command ensures:
- The user account with username `admin` exists.
- The email is set to `esan3125@gmail.com`.
- The password is set to `ish@npoudel888`.
- Both `is_staff` and `is_superuser` are set to `True`.
- The linked `Profile` record has `is_main_admin = True`.

---

## 2. Admin Panel Architecture & API Endpoints

The admin panel domain is implemented in `backend/apps/admin_panel` and exposed under `/api/v1/admin-panel/`.

### Permissions
1. **`IsAdminUser`** (`apps.admin_panel.permissions.IsAdminUser`):
   - Requires `request.user.is_authenticated` and `request.user.is_staff == True`.
   - Grants read-only access to the Admin Dashboard (viewing user directory, search, metrics, and catalog stats).
2. **`IsMainAdminUser`** (`apps.admin_panel.permissions.IsMainAdminUser`):
   - Requires `is_main_admin_user(request.user) == True`.
   - Protects administrative write operations: promoting users, demoting admins, creating new admin accounts, and deleting users.

### Main Admin Guard Logic (`is_main_admin_user`)
Defined in `apps/users/models.py`:
```python
def is_main_admin_user(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", True):
        return False
    profile = getattr(user, "profile", None)
    if profile and getattr(profile, "is_main_admin", False):
        return True
    if getattr(user, "is_superuser", False) and user.get_username() == "admin":
        return True
    return False
```
**Protection Guarantee**:
- The main administrator cannot be demoted, deleted, or stripped of admin privileges by anyone (including attempts by other staff admins, malicious requests, or accidental self-demotion).
- If the main administrator changes their username (e.g. from `admin` to a personalized handle), the `profile.is_main_admin` flag persists, ensuring they retain all owner rights and protection.

### API Endpoints
| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/admin-panel/stats/` | `IsAdminUser` | Returns counts: `total_users`, `total_admins`, `total_movies`, `total_ratings`. |
| `GET` | `/api/v1/admin-panel/users/?search=&role=` | `IsAdminUser` | Paginated user directory with search (username, email, display name) and role filter (`admin`, `user`, or `all`). |
| `POST` | `/api/v1/admin-panel/users/create-admin/` | `IsMainAdminUser` | Creates a new staff administrator (`is_staff=True`, `is_superuser=False`). |
| `POST` | `/api/v1/admin-panel/users/<id>/promote/` | `IsMainAdminUser` | Promotes a standard member to staff administrator (`is_staff=True`). |
| `POST` | `/api/v1/admin-panel/users/<id>/demote/` | `IsMainAdminUser` | Demotes an administrator back to member status. Rejects attempts to demote the main admin. |
| `DELETE` | `/api/v1/admin-panel/users/<id>/delete/` | `IsMainAdminUser` | Permanently removes an account. Rejects attempts to delete the main admin. |

---

## 3. Self-Service Profile & Credential Management

Users (including both normal members and administrators) can manage their own credentials and cinema profile directly via the backend API and the frontend UI.

### Endpoints
| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/users/me/` | `IsAuthenticated` | Returns current user details, including `is_staff`, `is_superuser`, `is_main_admin`, and `profile`. |
| `PATCH` | `/api/v1/users/me/` | `IsAuthenticated` | Self-service update for `username` and/or `email`. |
| `POST` | `/api/v1/users/me/password/` | `IsAuthenticated` | Self-service password change with current password verification. Updates session hash to prevent logout. |
| `GET` / `PATCH` | `/api/v1/users/me/profile/` | `IsAuthenticated` | Manages `display_name`, `bio`, `is_film_student`, and `favorite_genres`. |

---

## 4. Robust Input Validation Rules

Strict validation is enforced consistently across both the backend serializers/validators and the frontend forms:

### Username Rules (`validate_custom_username`)
- Length: 3 to 30 characters.
- Characters: Alphanumeric characters, underscores (`_`), and hyphens (`-`) only (`^[a-zA-Z0-9_-]{3,30}$`).
- Uniqueness: Case-insensitive uniqueness check against all existing accounts (excluding the user's own account on update).
- Rejects spaces, punctuation, symbols, and empty/whitespace-only input.

### Email Rules (`validate_custom_email`)
- Format: Compliant with RFC email specifications via Django's `EmailValidator`.
- Typo Domains: Detects and rejects common misspelled domains (e.g. `gmail.co`, `gmail.con`, `gmail.cmo`, `yahoo.co`, `hotmail.co`, `outlook.co`, `icloud.co`) with helpful suggestions.
- Gmail Enforcement: Any email with a domain matching `gmail.*` **must** end with `@gmail.com` (e.g. `gmail.org`, `gmail.net`, `gmail.co` are strictly rejected).
- TLD Validation: Top-level domain must be between 2 and 24 alphabetic characters (`^[a-zA-Z]{2,24}$`).
- Duplicate Rejection: Case-insensitive check ensuring no two accounts share an email.

### Password Rules (`validate_custom_password` & `password_validation`)
- Minimum Length: At least 8 characters.
- Complexity:
  - Must contain at least one letter (`[a-zA-Z]`).
  - Must contain at least one digit or special character (`[0-9!@#$%^&*()_+\-=\[\]{};':"\\|,.<>/?~`]`).
- Current Password Verification: Must provide correct existing password to change password.
- Confirmation: New password and confirm password inputs must match.
- Django Validators: Subject to standard Django password similarity and common password checks.

---

## 5. Frontend Routes & UI Implementation

### Routes
1. **`/account` (`frontend/src/pages/Account.tsx`)**:
   - **Account Credentials Card**: Editable username and email with instant client-side validation and server-side error mapping.
   - **Change Password Card**: Inputs for current password, new password, and confirmation password with password strength hints.
   - **Cinema Profile Card**: Display name, bio, film student toggle, and genre preferences.
   - **Admin Console Card (Sidebar)**: Shown only when `user.is_staff == true`. Displays administrator badge (`Main Administrator` or `Staff Admin`) and a direct link to the Admin Dashboard.
2. **`/admin` (`frontend/src/pages/AdminDashboard.tsx`)**:
   - Protected route: Redirects non-staff users to `/`.
   - **Header**: Shows administrator status pill with owner distinction.
   - **Quick Metrics Grid**: Real-time display of Total Users, Total Administrators, Catalog Movies, and Community Ratings.
   - **Add New Admin Modal**: Modal form for the main administrator to create new staff administrators.
   - **User Management Table**:
     - Search bar filtering by username, email, or display name.
     - Role filter tabs: "All Users", "Admins Only", "Members".
     - Badges: `Main Admin` (Gold), `Staff Admin` (Blue), `Member` (Gray).
     - Guarded Actions:
       - Main admin is tagged with `Protected` (cannot be demoted or deleted).
       - Main admin can promote members to admin, demote other admins, or delete accounts.
       - Staff admins see a "Managed by Main Admin" notice with write buttons disabled/hidden.
3. **Navbar Navigation (`frontend/src/components/Layout.tsx`)**:
   - If `user?.is_staff`, dynamically appends an **"Admin"** link (`/admin`) into the main navigation.

---

## 6. Verification Results

All automated verification checks and test suites were executed and passed with zero failures:

### Backend Automated Test Suite (`scripts/verify_admin_and_auth.py`)
- **Initial Admin Verification**:
  - Account `admin` verified (`esan3125@gmail.com`, `is_staff=True`, `is_superuser=True`, `is_main_admin=True`).
  - Authenticated successfully with `ish@npoudel888`.
- **Self-Service Credential Management**:
  - `[PASS]` Valid username update persisted.
  - `[PASS]` Short username (<3 chars) rejected (400).
  - `[PASS]` Invalid username characters rejected (400).
  - `[PASS]` Duplicate username rejected (400).
  - `[PASS]` Valid email update persisted.
  - `[PASS]` Typo domain (`gmail.co`) rejected (400).
  - `[PASS]` Invalid Gmail TLD (`gmail.org`) rejected (400).
  - `[PASS]` Duplicate email rejected (400).
  - `[PASS]` Incorrect current password rejected (400).
  - `[PASS]` Weak new password rejected (400).
  - `[PASS]` Password mismatch rejected (400).
  - `[PASS]` Valid password change succeeded and authenticated.
- **Admin Dashboard & Management**:
  - `[PASS]` Admin user list returned paginated accounts.
  - `[PASS]` Admin stats returned total counts for users, admins, movies, ratings.
  - `[PASS]` Main admin created new admin `curator_sarah`.
  - `[PASS]` Main admin promoted user to staff admin.
  - `[PASS]` Main admin demoted user from staff admin.
  - `[PASS]` Main admin removed user.
- **Main Admin Protection Guards**:
  - `[PASS]` Demoting main admin blocked with `The main admin cannot be demoted, deleted, or stripped of admin privileges.`
  - `[PASS]` Deleting main admin blocked.
- **Permission Bounds for Other Admins**:
  - `[PASS]` Staff admin can view user directory.
  - `[PASS]` Staff admin cannot create new admins (403 Forbidden).
  - `[PASS]` Staff admin cannot promote users (403 Forbidden).
  - `[PASS]` Staff admin cannot demote users (403 Forbidden).
  - `[PASS]` Staff admin cannot delete users (403 Forbidden).
- **Owner Privilege Persistence**:
  - `[PASS]` Main admin changed username to `ishan_lead` and retained full owner privileges.

### Frontend Verification
- `npm test`: 21/21 tests passed across 3 test suites (`src/api/playback.test.ts`, `src/api/client.test.ts`, `src/components/StarRating.test.tsx`).
- `npm run build`: Production build succeeded (`tsc -b && vite build`) with zero TypeScript errors or warnings.
- `backend/manage.py check`: Django system check identified 0 issues.
- `backend/manage.py spectacular --file docs/openapi.yaml`: Generated OpenAPI schema with 0 errors and 0 warnings.
