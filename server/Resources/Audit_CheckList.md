![power-bi-logo]()

**Power BI Dashboard Audit Checklist**

![]()

**Audit Date:**

**Scoring Guide:**

**Report Name:**

**Score**

**Description**

**Auditee:**

2

Fully Compliant — requirement is met completely

**Dept. of Auditee:**

1

Partially Compliant — requirement is partially met or inconsistently applied

**Auditor:**

0

Non-Compliant — requirement is not met

**Dept. of Auditor:**

N/A

Not applicable to this report

**Checklist:**

**Section**

#

**Checkpoint**

**Score**

**Comments**

**Backend:**

**Power BI License & Installation**

1

Power BI Desktop installed via approved company channel

**Template**

2

Report is built using the approved organizational template

**Template**

3

Report Owner and Developer names are filled in on the Document Control page within the template

**Data Connections**

4

Only approved data sources are used

**Data Connections**

5

No Excel exports from any system are used as a data source

**Data Connections**

6

Excel files are hosted on SharePoint and connected via a live URL (if applicable)

**Data Connections**

7

Connection mode (Import / DirectQuery) is appropriate and approved where required

**Data Connections**

8

SAP Datasphere connector installed via Software Center (if applicable)

**Data Connections**

9

SAP Datasphere connection points only to Consumption Layer objects (if applicable)

**Data Connections**

10

Where the same data exists in a system database, Excel connection must be replaced with a proper database connection (if applicable)

**Data Connections**

11

Databricks connection established via approved method (if applicable)

**Data Preparation (Power Query)**

12

Unused columns removed before closing Power Query

**Data Preparation (Power Query)**

13

Duplicate rows removed where not intentional

**Data Preparation (Power Query)**

14

Data types set explicitly for all columns

**Data Preparation (Power Query)**

15

Null values handled explicitly

**Data Preparation (Power Query)**

16

Business logic must not be implemented in Power Query (it belongs in DAX)

**Data Preparation (Power Query)**

17

Table naming convention followed (Fct\_, Dim\_, Br\_, Stg\_)

**Data Preparation (Power Query)**

18

Staging and helper tables hidden from report view

**Data Preparation (Power Query)**

19

Reference or staging queries disabled from load where applicable

**Data Preparation (Power Query)**

20

Power Query queries organized into folders by table type

**Data Modeling**

21

Star schema applied where possible

**Data Modeling**

22

Snowflake or flat models justified where star schema is not feasible

**Data Modeling**

23

All relationships are single-direction unless explicitly justified

**Data Modeling**

24

No circular relationships exist in the model

**Data Modeling**

25

Measures preferred over calculated columns for aggregation and business logic

**Data Modeling**

26

All measures stored in a dedicated measure table

**Data Modeling**

27

Measures formatted with line breaks and comments where needed

**Data Modeling**

28

Column names are user‑friendly and written in plain English

**Data Modeling**

29

Technical columns prefixed consistently (e.g. \_SortOrder)

**Data Modeling**

30

Date Table exists and marked correctly where time intelligence is used

**DAX Standards**

31

Measures are readable, maintainable, and reusable

**DAX Standards**

32

Business logic is not duplicated across multiple measures

**Performance**

33

Unnecessary high‑cardinality columns avoided

**Performance**

34

Performance Analyzer used to review slow visuals

**Performance**

35

DirectQuery models reviewed for aggregations where applicable

**Performance**

36

Report load time is reasonable and acceptable for business use

**Pre‑Publication Testing**

37

All visuals load without errors

**Pre‑Publication Testing**

38

Filters and slicers function as expected

**Pre‑Publication Testing**

39

At least 3 data values cross‑checked against source system

**Pre‑Publication Testing**

40

Report renders correctly in Power BI Desktop and Power BI Service

**Pre‑Publication Testing**

41

Scheduled refresh completed successfully at least once in Service

**Pre‑Publication Testing**

42

Business logic validated (e.g. balance sheet checks)

**Pre‑Publication Testing**

43

Faulty or inconsistent data flagged and addressed

**Pre‑Publication Testing**

44

Report Owner confirmed content accuracy in writing

**Pre‑Publication Testing**

45

RLS roles tested using “View as” where applicable

**Semantic Model Reuse & Governance**

46

Existing semantic model reused where applicable

**Semantic Model Reuse & Governance**

47

Permissions requested from semantic model owner before reuse

**Frontend:**

**Power BI License & Installation**

48

Power BI Pro license obtained before any publishing activity

**Report Design**

49

Page 1 is a Summary or Overview page

**Report Design**

50

Every page has a clear, descriptive title

**Report Design**

51

Visual types are appropriate; no 3D charts or pie charts with more than 6 slices

**Report Design**

52

Slicers are consistently placed and labelled

**Report Design**

53

Sync slicers used where filters apply across pages

**Report Design**

54

Minimum font size of 9pt maintained throughout

**Quality Checks**

55

Report renders correctly across devices and browsers

**Quality Checks**

56

Data behavior validated against known business rules

**Publication**

57

Published to an approved named workspace

**Publication**

58

Report placed in the correct use-case folder within the workspace

**Publication**

59

Prior version moved to Archive subfolder before republishing

**Publication**

60

Report description completed in Power BI Service (purpose, owner, sources, refresh schedule)

**Publication**

61

Sensitivity label assigned (Public / Internal / Confidential)

**Publication**

62

Report registered in Linde plc. Report Inventory within one month of publication

**Data Refresh**

63

Data Gateway configured for the workspace

**Data Refresh**

64

Scheduled refresh configured for all live reports

**Data Refresh**

65

Refresh frequency aligned with actual source data update frequency

**Data Refresh**

66

Refresh failure alerts enabled and directed to Report Developer and Workspace Admin

**Data Refresh**

67

Refresh scheduled during off-peak hours

**Access Control (Service)**

68

Report access does not exceed source system access rights

**Access Control (Service)**

69

Workspace roles assigned on least privilege basis

**Access Control (Service)**

70

Security groups used for granting access to multiple users

**Access Control (Service)**

71

Guest user access (if any) approved by regional IT Security team

**Version Control & Maintenance**

72

Document Control page in the .pbix file is up to date

**Version Control & Maintenance**

73

Document Control Excel log is maintained with a revision log

**Version Control & Maintenance**

74

Latest published .pbix used as the base for the most recent update

**Version Control & Maintenance**

75

Archived versions retained for rollback

**Version Control & Maintenance**

76

Report reviewed when logic, data sources, or KPIs change

**Version Control & Maintenance**

77

Report reviewed at least once every 6 months

**Overall Scores:**

**Type**

**Score (Out of 77)**

**%**

Fully Compliant

\_/77

Partially Compliant

\_/77

Non-Compliant

\_/77

**Follow-Up Process:**

**Step**

**Action**

1

Auditor shares findings with the Report Developer and Report Owner within \_\_ business days of the audit

2

Developer and Owner review findings and agree on a remediation plan within \_\_ business days of receiving the findings

3

Agreed actions are completed by the defined remediation deadline

4

Auditor performs a follow-up review to confirm all items have been addressed

5

If items remain unresolved beyond the deadline, the matter is referred to the relevant team manager for support

_Note: This process is intended to be collaborative. The goal is to bring reports up to standard, not to assign blame. The Data Analytics Team is available to assist with any remediation._