-- ==============================================================================
-- ClubSphere — Optimized T-SQL Views for Power BI Reporting & Institutional Analytics
-- Connects directly via Power BI Desktop -> Get Data -> Azure SQL Database
-- ==============================================================================

-- 1. Primary Power BI Reporting View: Club Analytics Summary
CREATE OR ALTER VIEW vw_club_analytics_summary AS
SELECT
    c.ClubId,
    c.Name AS ClubName,
    c.Status AS ClubStatus,
    p.ProgramId,
    p.FullName AS ProgramName,
    b.BranchId,
    b.Name AS BranchName,
    u.UserId AS ManagerUserId,
    u.FullName AS ManagerName,
    COUNT(DISTINCT CASE WHEN cm.Status = 'active' THEN cm.MembershipId END) AS ActiveMembersCount,
    COUNT(DISTINCT CASE WHEN cm.Status = 'requested' THEN cm.MembershipId END) AS PendingMembersCount,
    COUNT(DISTINCT CASE WHEN cm.Status = 'removed' THEN cm.MembershipId END) AS RemovedMembersCount,
    COUNT(DISTINCT CASE WHEN cm.Status = 'active' AND cm.Role <> 'Member' THEN cm.MembershipId END) AS LeadershipCount,
    COUNT(DISTINCT e.EventId) AS TotalEventsCount,
    COUNT(DISTINCT CASE WHEN e.Status = 'published' THEN e.EventId END) AS PublishedEventsCount,
    COUNT(DISTINCT CASE WHEN e.Status = 'completed' THEN e.EventId END) AS CompletedEventsCount,
    COUNT(DISTINCT CASE WHEN er.Status = 'confirmed' THEN er.RegistrationId END) AS ConfirmedRegistrationsCount,
    COUNT(DISTINCT a.AttendanceId) AS TotalAttendanceCount,
    MAX(cm.JoinedAt) AS LatestMembershipActivityAt,
    MAX(e.EventDate) AS LatestEventDate,
    c.CreatedAt AS ClubCreatedAt
FROM Clubs c
INNER JOIN Programs p ON c.ProgramId = p.ProgramId
INNER JOIN Branches b ON p.BranchId = b.BranchId
INNER JOIN Users u ON c.ManagerUserId = u.UserId
LEFT JOIN ClubMemberships cm ON c.ClubId = cm.ClubId
LEFT JOIN Events e ON c.ClubId = e.ClubId
LEFT JOIN EventRegistrations er ON e.EventId = er.EventId
LEFT JOIN Attendance a ON e.EventId = a.EventId
GROUP BY
    c.ClubId,
    c.Name,
    c.Status,
    p.ProgramId,
    p.FullName,
    b.BranchId,
    b.Name,
    u.UserId,
    u.FullName,
    c.CreatedAt;
GO

-- 2. View: Event Registration Summary & Fill Rate
CREATE OR ALTER VIEW vw_EventRegistrationSummary AS
SELECT
    e.EventId,
    e.Title AS EventTitle,
    e.ClubId,
    c.Name AS ClubName,
    b.Name AS BranchName,
    p.FullName AS ProgramName,
    e.EventDate,
    e.RegistrationDeadline,
    e.Capacity,
    e.Status AS EventStatus,
    COUNT(CASE WHEN er.Status = 'confirmed' THEN 1 END) AS ConfirmedRegistrations,
    COUNT(CASE WHEN er.Status = 'waitlisted' THEN 1 END) AS WaitlistedRegistrations,
    COUNT(CASE WHEN er.Status = 'cancelled' THEN 1 END) AS CancelledRegistrations,
    CASE
        WHEN e.Capacity - COUNT(CASE WHEN er.Status = 'confirmed' THEN 1 END) < 0 THEN 0
        ELSE e.Capacity - COUNT(CASE WHEN er.Status = 'confirmed' THEN 1 END)
    END AS SeatsLeft,
    CASE
        WHEN e.Capacity > 0 THEN
            ROUND((CAST(COUNT(CASE WHEN er.Status = 'confirmed' THEN 1 END) AS FLOAT) / e.Capacity) * 100, 2)
        ELSE 0.0
    END AS FillRatePercent
FROM Events e
INNER JOIN Clubs c ON e.ClubId = c.ClubId
INNER JOIN Programs p ON c.ProgramId = p.ProgramId
INNER JOIN Branches b ON p.BranchId = b.BranchId
LEFT JOIN EventRegistrations er ON e.EventId = er.EventId
GROUP BY
    e.EventId,
    e.Title,
    e.ClubId,
    c.Name,
    b.Name,
    p.FullName,
    e.EventDate,
    e.RegistrationDeadline,
    e.Capacity,
    e.Status;
GO

-- 3. View: Event Attendance Rate
CREATE OR ALTER VIEW vw_AttendanceRate AS
SELECT
    e.EventId,
    e.Title AS EventTitle,
    c.ClubId,
    c.Name AS ClubName,
    e.EventDate,
    COUNT(DISTINCT er.UserId) AS ConfirmedRegistrations,
    COUNT(DISTINCT a.UserId) AS AttendedCount,
    CASE
        WHEN COUNT(DISTINCT er.UserId) > 0 THEN
            ROUND((CAST(COUNT(DISTINCT a.UserId) AS FLOAT) / COUNT(DISTINCT er.UserId)) * 100, 2)
        ELSE 0.0
    END AS AttendanceRatePercent
FROM Events e
INNER JOIN Clubs c ON e.ClubId = c.ClubId
LEFT JOIN EventRegistrations er ON e.EventId = er.EventId AND er.Status = 'confirmed'
LEFT JOIN Attendance a ON e.EventId = a.EventId
GROUP BY
    e.EventId,
    e.Title,
    c.ClubId,
    c.Name,
    e.EventDate;
GO

-- 4. View: Club Activity & Health Metrics
CREATE OR ALTER VIEW vw_ClubActivity AS
SELECT
    c.ClubId,
    c.Name AS ClubName,
    b.BranchId,
    b.Name AS BranchName,
    p.ProgramId,
    p.FullName AS ProgramName,
    u.FullName AS ManagerName,
    c.Status AS ClubStatus,
    c.CreatedAt AS ClubCreatedDate,
    COUNT(DISTINCT cm.MembershipId) AS ActiveMembersCount,
    COUNT(DISTINCT e.EventId) AS TotalEventsHosted,
    COUNT(DISTINCT CASE WHEN e.Status = 'published' THEN e.EventId END) AS PublishedEvents,
    COUNT(DISTINCT CASE WHEN e.Status = 'completed' THEN e.EventId END) AS CompletedEvents
FROM Clubs c
INNER JOIN Programs p ON c.ProgramId = p.ProgramId
INNER JOIN Branches b ON p.BranchId = b.BranchId
INNER JOIN Users u ON c.ManagerUserId = u.UserId
LEFT JOIN ClubMemberships cm ON c.ClubId = cm.ClubId AND cm.Status = 'active'
LEFT JOIN Events e ON c.ClubId = e.ClubId
GROUP BY
    c.ClubId,
    c.Name,
    b.BranchId,
    b.Name,
    p.ProgramId,
    p.FullName,
    u.FullName,
    c.Status,
    c.CreatedAt;
GO

-- 5. View: Branch Student Participation
CREATE OR ALTER VIEW vw_BranchParticipation AS
SELECT
    b.BranchId,
    b.Name AS BranchName,
    FORMAT(er.RegisteredAt, 'yyyy-MM') AS RegistrationYearMonth,
    COUNT(DISTINCT er.UserId) AS UniqueStudentParticipants,
    COUNT(er.RegistrationId) AS TotalRegistrationCount
FROM EventRegistrations er
INNER JOIN Users u ON er.UserId = u.UserId
INNER JOIN Programs p ON u.ProgramId = p.ProgramId
INNER JOIN Branches b ON p.BranchId = b.BranchId
WHERE er.Status = 'confirmed'
GROUP BY
    b.BranchId,
    b.Name,
    FORMAT(er.RegisteredAt, 'yyyy-MM');
GO
