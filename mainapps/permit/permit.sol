pragma solidity ^0.8.0;

contract PermissionManager {
    // Global Permission Categories
    struct PermissionCategory {
        uint256 id;
        string name;
        string description;
        string icon;
    }
    mapping(uint256 => PermissionCategory) public permissionCategories;
    uint256 public permissionCategoryCount;

    // Global Custom Permissions
    struct CustomPermission {
        uint256 id;
        string codename;
        string name;
        string description;
        uint256 categoryId;
    }
    mapping(uint256 => CustomPermission) public customPermissions;
    uint256 public customPermissionCount;

    // Tenant-Specific Staff Groups
    struct StaffGroup {
        uint256 id;
        uint256 companyId;
        string name;
        string description;
        uint256[] permissionIds;
    }
    mapping(uint256 => StaffGroup) public staffGroups;
    uint256 public staffGroupCount;

    // Tenant-Specific Staff Roles
    struct StaffRole {
        uint256 id;
        uint256 companyId;
        string name;
        string description;
        uint256[] permissionIds;
    }
    mapping(uint256 => StaffRole) public staffRoles;
    uint256 public staffRoleCount;

    // Tenant-Specific Role Assignments
    struct StaffRoleAssignment {
        uint256 id;
        address userAddress;
        uint256 roleId;
        uint256 startDate;
        uint256 endDate;
        bool isActive;
    }
    mapping(uint256 => StaffRoleAssignment) public staffRoleAssignments;
    uint256 public staffRoleAssignmentCount;

    // User Data
    struct UserData {
        address userAddress;
        uint256 companyId;
        uint256[] directPermissionIds;
        uint256[] groupIds;
        uint256[] roleAssignmentIds;
    }
    mapping(address => UserData) public users;

    // KYC Status
    mapping(address => bool) public isKYCVerified;

    // Events
    event PermissionCategoryAdded(uint256 indexed id, string name);
    event CustomPermissionAdded(uint256 indexed id, string codename);
    event StaffGroupAdded(uint256 indexed id, uint256 companyId, string name);
    event StaffRoleAdded(uint256 indexed id, uint256 companyId, string name);
    event RoleAssigned(uint256 indexed id, address userAddress, uint256 roleId);
    event DirectPermissionGranted(address indexed userAddress, uint256 permissionId);
    event KYCVerified(address indexed userAddress, bool verified);

    // Add Permission Category
    function addPermissionCategory(string memory name, string memory description, string memory icon) public {
        permissionCategoryCount++;
        permissionCategories[permissionCategoryCount] = PermissionCategory(permissionCategoryCount, name, description, icon);
        emit PermissionCategoryAdded(permissionCategoryCount, name);
    }

    // Add Custom Permission
    function addCustomPermission(string memory codename, string memory name, string memory description, uint256 categoryId) public {
        require(categoryId <= permissionCategoryCount, "Invalid category ID");
        customPermissionCount++;
        customPermissions[customPermissionCount] = CustomPermission(customPermissionCount, codename, name, description, categoryId);
        emit CustomPermissionAdded(customPermissionCount, codename);
    }

    // Add Staff Group
    function addStaffGroup(uint256 companyId, string memory name, string memory description, uint256[] memory permissionIds) public {
        staffGroupCount++;
        staffGroups[staffGroupCount] = StaffGroup(staffGroupCount, companyId, name, description, permissionIds);
        emit StaffGroupAdded(staffGroupCount, companyId, name);
    }

    // Add Staff Role
    function addStaffRole(uint256 companyId, string memory name, string memory description, uint256[] memory permissionIds) public {
        staffRoleCount++;
        staffRoles[staffRoleCount] = StaffRole(staffRoleCount, companyId, name, description, permissionIds);
        emit StaffRoleAdded(staffRoleCount, companyId, name);
    }

    // Assign Role to User
    function assignRole(address userAddress, uint256 roleId, uint256 startDate, uint256 endDate) public {
        require(users[userAddress].companyId != 0, "User not registered");
        require(roleId <= staffRoleCount, "Invalid role ID");
        staffRoleAssignmentCount++;
        staffRoleAssignments[staffRoleAssignmentCount] = StaffRoleAssignment(
            staffRoleAssignmentCount,
            userAddress,
            roleId,
            startDate,
            endDate,
            true
        );
        users[userAddress].roleAssignmentIds.push(staffRoleAssignmentCount);
        emit RoleAssigned(staffRoleAssignmentCount, userAddress, roleId);
    }

    // Add Direct Permission to User
    function addDirectPermissionToUser(address userAddress, uint256 permissionId) public {
        UserData storage userData = users[userAddress];
        require(userData.companyId != 0, "User not registered");
        require(permissionId <= customPermissionCount, "Invalid permission ID");
        for (uint256 i = 0; i < userData.directPermissionIds.length; i++) {
            if (userData.directPermissionIds[i] == permissionId) {
                return; // Already has permission
            }
        }
        userData.directPermissionIds.push(permissionId);
        emit DirectPermissionGranted(userAddress, permissionId);
    }

    // Register User
    function registerUser(address userAddress, uint256 companyId) public {
        require(users[userAddress].companyId == 0, "User already registered");
        users[userAddress] = UserData(userAddress, companyId, new uint256[](0), new uint256[](0), new uint256[](0));
    }

    // Set KYC Status
    function setKYCVerified(address userAddress, bool verified) public {
        isKYCVerified[userAddress] = verified;
        emit KYCVerified(userAddress, verified);
    }

    // Check Permission
    function hasPermission(address userAddress, uint256 permissionId) public view returns (bool) {
        UserData storage userData = users[userAddress];
        // Check direct permissions
        for (uint256 i = 0; i < userData.directPermissionIds.length; i++) {
            if (userData.directPermissionIds[i] == permissionId) {
                return true;
            }
        }
        // Check group permissions
        for (uint256 i = 0; i < userData.groupIds.length; i++) {
            StaffGroup storage group = staffGroups[userData.groupIds[i]];
            for (uint256 j = 0; j < group.permissionIds.length; j++) {
                if (group.permissionIds[j] == permissionId) {
                    return true;
                }
            }
        }
        // Check role permissions
        for (uint256 i = 0; i < userData.roleAssignmentIds.length; i++) {
            StaffRoleAssignment storage assignment = staffRoleAssignments[userData.roleAssignmentIds[i]];
            if (assignment.isActive && (assignment.endDate == 0 || block.timestamp <= assignment.endDate)) {
                StaffRole storage role = staffRoles[assignment.roleId];
                for (uint256 j = 0; j < role.permissionIds.length; j++) {
                    if (role.permissionIds[j] == permissionId) {
                        return true;
                    }
                }
            }
        }
        return false;
    }
}