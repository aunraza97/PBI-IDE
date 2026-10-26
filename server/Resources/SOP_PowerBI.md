![]()

**SOP Document**

Enterprise Dashboard Development

Using Power BI

**![]()**

Contents

[**Purpose:** 4](#_Toc229581249)

[**Scope and Applicability:** 4](#_Toc229581250)

[**Roles and Responsibilities:** 4](#_Toc229581251)

[**Control Enforcement and Compliance:** 5](#_Toc229581252)

[**Backend:** 5](#_Toc229581253)

[1\. Development Workflow: 5](#_Toc229581254)

[1.1. Requesting Access and Getting Started: 5](#_Toc229581255)

[1.2. Downloading the Report Template: 6](#_Toc229581256)

[1.3. Connecting to Data Sources: 6](#_Toc229581257)

[1.4. Data Cleaning and Transformation (Power Query): 6](#_Toc229581258)

[1.5. Data Modeling Standards: 8](#_Toc229581259)

[1.6. DAX Standards: 11](#_Toc229581260)

[1.7. Performance Optimization: 11](#_Toc229581261)

[1.8. Pre-Publication Testing: 12](#_Toc229581262)

[2\. Access Control: 13](#_Toc229581263)

[2.1. Access Control on Power BI Desktop: 13](#_Toc229581264)

[2.2. Enforcement & Consequences 13](#_Toc229581265)

[3\. Data Source Specific Guidelines: 14](#_Toc229581266)

[3.1. SAP Datasphere: 14](#_Toc229581267)

[3.2. Databricks: 15](#_Toc229581268)

[3.3. Excel / SharePoint: 15](#_Toc229581269)

[4\. Quality & Assurance: 16](#_Toc229581270)

[4.1. Semantic Model Reuse: 16](#_Toc229581271)

[**Frontend:** 16](#_Toc229581272)

[1\. Requesting a Power BI Pro License 16](#_Toc229581273)

[2\. Report Design and Layout 17](#_Toc229581274)

[2.1. Page structure: 17](#_Toc229581275)

[2.2. Filters and slicers: 17](#_Toc229581276)

[3\. Quality Checks: 17](#_Toc229581277)

[3.1. Business Logic Validation: 17](#_Toc229581278)

[3.2. Validation Table 18](#_Toc229581279)

[3.3. Faulty Data 18](#_Toc229581280)

[4\. Publication and Workspace Management 18](#_Toc229581281)

[4.1. Folder Structure: 19](#_Toc229581282)

[4.2. Data Refresh Frequency: 19](#_Toc229581283)

[4.3. Power BI App Registration 20](#_Toc229581284)

[5\. Access Control on Power BI Service: 20](#_Toc229581285)

[6\. Maintenance and Version Control 21](#_Toc229581286)

[6.1. Version Control on Local Machine: 21](#_Toc229581287)

[6.2. Version Control on Power BI Workspace: 22](#_Toc229581288)

[6.3. Change Control: 22](#_Toc229581289)

[6.4. Decommissioning 22](#_Toc229581290)

[**Audit, Review & Compliance Monitoring** 23](#_Toc229581291)

[**Exceptions, Incidents & Deviations** 24](#_Toc229581292)

[Exceptions: 24](#_Toc229581293)

[Incidents: 24](#_Toc229581294)

[Deviations: 24](#_Toc229581295)

[**Document Control** 24](#_Toc229581296)

[**Power BI & Other Relevant Documentation :** 26](#_Toc229581297)

# **Purpose:**

This document establishes the standard procedure for developing, publishing, and maintaining Power BI dashboards across the organization. It applies to any team that produces or consumes Power BI reports, regardless of business unit or region.

Consistent standards ensure that a dashboard built in one region is readable, replicable, easily maintainable, and structurally familiar to any Linde employee. This document exists to support that consistency and to provide a clear, repeatable process for all contributors.

# **Scope and Applicability:**

This SOP applies to:

*   All Power BI Desktop (.pbix) reports intended for organizational use
*   Reports published to any Power BI Service workspace
*   PBi Dashboards embedded in other tools or portals
*   All teams (analytics, finance, operations, supply chain, commercial, or otherwise) that build or maintain Power BI reports

Teams using other reporting tools should refer to their respective SOPs. Where Power BI is the chosen delivery tool, this document governs.

# **Roles and Responsibilities:**

Role

Responsibility

Report Developer

Builds and maintains the .pbix file; responsible for adhering to all standards in this SOP

Report Owner

Business-side accountable person; approves content accuracy before publication

Data Owner

Responsible for the underlying data source; confirms data accuracy and manages access rights

Workspace Admin

Manages the Power BI Service workspace; controls publishing permissions

Data Analytics Team

Defines and governs standards; reviews reports upon request or during audits

Every report must have a named Report Owner and a named Report Developer on record before publication.

This information can be documented in the template under the section “Document Control”.

# **Control Enforcement and Compliance:**

The rules defined in this SOP are classified into three levels to distinguish between enforceable controls and guidance:

*   **Mandatory Control:** This rule must always be followed. There are no exceptions and compliance will be checked during every audit.
*   **Strong Recommendation:** This rule is expected to be followed in most cases. It is not strictly enforced but developers are accountable for applying it as standard practice.
*   **Optional / Good Practice:** This is a suggestion to help you build better reports. It is not enforced and there are no consequences if you choose not to follow it.

Throughout this SOP, each rule is labelled accordingly so that developers and auditors can clearly distinguish between what is required and what is advisory.

The Data Analytics Team is responsible for defining, maintaining, and enforcing the standards in this SOP. Non-compliance identified during an audit will be communicated to the Report Developer, the Report Owner, and their respective team manager. Repeated or unresolved non-compliance will be escalated to senior management.

# **Backend:**

## Development Workflow:

### Requesting Access and Getting Started:

Power BI Desktop must be installed through the company's approved software distribution channel. Downloading Power BI Desktop from external sources is not permitted, as it falls outside the organization's security and compliance controls.

To request access and set up your environment, please follow the steps outlined in the Getting Started Guide.

SharePoint Link: [Microsoft Power BI - Getting Started](https://lindegroup.sharepoint.com/sites/LEGBLITSystems/SitePages/Microsoft%20Power%20BI/Help/Getting%20Started.aspx)

Video Tutorial Link: [Tutorial\_PowerBI.mp4](https://lindegroup.sharepoint.com/:v:/r/sites/msteams_48df48/Shared%20Documents/General/90%20Getting%20Started%20-%20Videos/Tutorial_PowerBI.mp4?csf=1&web=1&e=zcyC48)

### Downloading the Report Template:

All Power BI reports must be built using the approved organizational template. The template contains the corporate color palette, standard fonts, a pre-built header layout, and a side-panel for functional buttons.

Downloading the template before beginning any development is strongly recommended.

The latest version of the template is available here:

Power BI Template: [Template.pbix](https://lindegroup-my.sharepoint.com/:u:/r/personal/e6nc70_linde-le_com/Documents/Documents/Project_DA/Power%20BI_SOP/Template.pbix?csf=1&web=1&e=SATcRu)

### Connecting to Data Sources:

Once the template is open, the first step is establishing connections to the required data sources. The following sources are commonly used in Power BI reports:

*   SAP Datasphere
*   SharePoint Lists
*   Excel files hosted on SharePoint
*   Databricks

For guidance on accessing data sources or requesting new ones, refer to Section 3.

### Data Cleaning and Transformation (Power Query):

All data cleaning and transformation work must be performed within Power Query before loading data into the model. Applying transformations outside of Power Query, directly on the model, makes the report harder to maintain.

**Data cleaning** refers to the process of identifying and correcting issues in the raw data before it is loaded into the model. This includes removing duplicate rows, replacing null values, correcting data types, removing irrelevant columns, and resolving structural inconsistencies such as mismatched formats or broken references.

**Data transformation** refers to reshaping or restructuring the data to make it suitable for modeling and reporting. This includes renaming columns, merging or appending queries, pivoting or unpivoting tables, splitting columns, and applying filtering logic that defines which rows are relevant to the report.

#### General best practices:

*   Remove all columns that are not required by the report before closing Power Query. Loading unused columns increases model size and degrades performance.
*   Remove duplicate rows where they are not intentional.
*   Replace null values explicitly, either with a meaningful default or a clear label such as "Unknown" or "Not Assigned”, rather than leaving nulls to surface in visuals.
*   Set data types explicitly for every column. Do not rely on Power Query's auto-detection. For example, Dates must be set to Date or DateTime.
*   Do not perform calculations or business logic in Power Query that belong in DAX. Use Power Query for shaping and cleaning only.
*   Optional but useful:
    *   Avoid using the first row as headers unless the source file genuinely requires it. This step often introduces errors when source file structures change.
    *   Keep transformation steps named clearly. Rename Power Query steps from default labels like "Changed Type1" to descriptive names like "Set Order Date as Date Type". This makes the query auditable.

#### Table Naming:

All tables loaded into the model must follow a consistent naming convention:

**Table Type**

**Prefix**

**Example**

Fact table

Fct\_

Fct\_SalesOrders

Dimension table

Dim\_

Dim\_Customer

**Optional**

Bridge / junction table

Br\_

Br\_ProductCategory

Staging / helper table

Stg\_

Stg\_RawExport

Inbound table

Inb\_

Inb\_RegionalMapping

Tables used purely for intermediate processing (such as staging tables, helper queries, or parameter tables) must be hidden from the report view. Right-click the table in the Fields pane and select "Hide in report view". This keeps the model clean and prevents end users from accidentally referencing unintended tables.

Inbound tables, reference queries and staging steps that feed into a final table should also be disabled from loading (right-click query > "Enable Load" unchecked) if their output is consumed by another query rather than used directly in the model.

_Note: The Inb\_ prefix is optional. In most cases, inbound tables are renamed directly as fact tables, which is equally acceptable. Use the Inb\_ prefix only when you need to distinguish the raw inbound layer from a cleaned or transformed fact table that sits alongside it in the model._

#### Folder Structure in Power Query:

Queries must be organized into folders within Power Query to maintain a clean and navigable workspace. The folder structure should mirror the table naming convention, grouping queries by their role in the model.

**Folder Name**

**Contents**

Fct or Fact Tables

All fact tables

Dim or dimension Tables

All dimension tables

Br or Bridge Tables

All bridge or junction tables

Stg, Stage or Helper Tables

Staging, helper, and intermediate queries

Inbound Tables

Incoming data

### Data Modeling Standards:

After closing Power Query, the next step is building the data model. Visuals should not be built until the model structure is complete and validated.

#### Model structure:

The standard model pattern is a **star schema**: fact tables at the center, connected to dimension tables via single, one-to-many relationships.

![]()

Figure 1: Star Schema Power BI Model

_Source : https://help.zebrabi.com/kb/power-bi/star-schema/_

_Note: It is not mandatory to achieve a star schema. However, the source data should always be evaluated to determine whether it can be modeled in this way._

Snowflake schemas should be avoided unless the source data structure makes them unavoidable, because they split dimension tables into multiple sub-tables that require additional joins to retrieve data. Power BI is optimized for flat star schema structures, and the more joins involved, the slower the queries and the harder the model becomes to read and maintain.

A flat table structure is acceptable only when the data is genuinely atomic, meaning no repeating attribute groups exist that could be separated into a dimension. Where dimension tables can be created, they should be. Flat, un-modeled outputs used purely for convenience are not an acceptable base for report visuals.

#### Relationships:

*   All relationships must be single direction unless a bidirectional relationship is explicitly required and documented within the report.
*   Only one active relationship can exist between two tables at a time. If a second relationship is needed between the same tables, it must be set as inactive and triggered within a specific DAX measure using the USERELATIONSHIP function.
*   Circular relationships must be resolved before the report is published. Power BI will automatically flag a circular dependency error
*   Relationship cardinality must be set correctly and verified manually. Power BI's auto-detection is a useful starting point, not a final answer.

#### Folder Structure in Data Model View:

Calculated columns can reside inside of a table, but measures must be stored in a dedicated, empty measure table. This table contains no data rows; it exists solely to organize measures.

Measure table can also be created from inside the power query using the following code. (To be pasted in Advanced Query)

![]()

Further segregation within the measure table is also useful but not mandatory. For example, grouping measures into subfolders by topic or calculation type. Two tools support this efficiently:

*   **Tabular Editor** is a free external tool that allows you to manage, group, and document measures more efficiently than the native Power BI interface. It is particularly useful for larger models with a high number of measures.

Download Link: [_https://tabulareditor.com/downloads_](https://tabulareditor.com/downloads)

*   **TMDL (Tabular Model Definition Language)** is a built-in Power BI Desktop view that lets you edit model metadata directly in code, including bulk-moving measures into folders in one operation.

#### Column naming:

*   Column names should be written in plain, readable English. Avoid abbreviations and underscores where a full word works just as well (e.g., Order Date rather than Ord\_Dt).
*   Technical columns used for sorting or internal processing, but not displayed to users, should be prefixed with an underscore (e.g., MonthSortOrder).
*   Where possible, technical or system-generated column names should be renamed directly in the source system (e.g. SAP Datasphere or Databricks) before the data reaches Power BI. This is the preferred approach as it ensures consistency across all consumers of that data.
*   If renaming at the source is not possible, all technical column names must be renamed in Power Query to clear, business-friendly labels before being loaded into the model. End users and other developers must never be exposed to raw technical naming from the source system.

#### Date table:

Every report that uses any time intelligence function must include a dedicated Date Table. Mark it as a Dim\_Date in the model settings. It must cover the full range of dates present in the data, with no gaps.

The Date Table must be created by referencing the date column from the fact table, ensuring the date range is always driven by the actual data in the model and not defined manually or arbitrarily.

### DAX Standards:

Measures must be readable and maintainable by someone other than the original author. As a rule of thumb, if a measure cannot be understood by a developer who did not write it, it needs better formatting or commenting.

Example of well-formatted DAX:

![]()

### Performance Optimization:

Reports should load within a reasonable time.

*   Load only the columns needed for the report. Where possible, restrict the columns at the source system level before the data reaches Power BI. If column restriction at the source is not possible, remove all unused columns in Power Query before closing.
*   Avoid loading text columns with a very large number of unique values (such as free-text descriptions) unless they are directly needed for filtering or display in the report. These columns consume significant memory and slow down the model without adding analytical value.
*   Use Power BI's Performance Analyzer (View > Performance Analyzer) to identify slow visuals before publishing.
*   Use the cross-filtering option to limit filtering to certain visuals when required. This can be configured by clicking on a visual, navigating to Format > Edit Interactions in the Power BI Desktop toolbar, and then selecting for each other visual on the page whether it should be filtered, highlighted, or unaffected when the selected visual is interacted with.

![]()

*   Where large fact tables require DirectQuery, consider using Aggregations to reduce query load on the source system.

### Pre-Publication Testing:

*   All visuals load without errors
*   All filters and slicers function as expected
*   At least 3 data values have been cross-checked against the source system
*   The report renders correctly in both Power BI Desktop and Power BI Service (browser)
*   A scheduled data refresh has completed successfully at least once in the Service environment
*   The Report Owner has reviewed and confirmed content accuracy in writing
*   If Row-Level Security (RLS) has been configured, verify that each defined role returns the correct and expected subset of data before publishing. Use the "View as" feature under “Modelling” in Power BI Desktop to test every role individually.

#### Required Evidence:

Completing the pre-publication checklist is not sufficient on its own. Developers must retain evidence that each check was performed, as this will be requested during audits. The following evidence must be available upon request:

*   **Owner Approval:** Written confirmation from the Report Owner approving the report content before publication. Email confirmation is acceptable.
*   **RLS Testing:** A screenshot or written record of the "View as" test results for every defined RLS role, confirming that each role returns the correct and expected data subset.
*   **Data Validation:** At least 3 data values must be cross-checked against the source system.

Evidence does not need to follow a specific format but must be retrievable and clearly linked to the report it relates to. It is the responsibility of the Report Developer to collect and retain this evidence.

## Access Control:

Access to published reports must reflect the access rights that exist at the source data level. Power BI must not grant broader visibility than the source system permits.

### Access Control on Power BI Desktop:

*   Row-Level Security (RLS) must be implemented for any report where different users should see different subsets of data (e.g., a regional manager seeing only their own region's figures).
*   RLS roles are defined in Power BI Desktop under the Modeling tab, using the Manage Roles option. Each role must be tested using the "View as" feature before the report is published.

### Enforcement & Consequences

The Data Analytics Team is responsible for monitoring and enforcing compliance for global dashboards with the access control standards defined in this SOP. The following consequences apply in cases of non-compliance:

*   Reports found to have incorrect or excessive access permissions will be flagged immediately and the Report Owner must resolve the issue within the agreed remediation timeline.
*   (If applicable) Reports published without the required RLS configuration will be taken offline until the correct security setup has been implemented and tested.
*   Workspace roles assigned beyond the least privilege principle will be reviewed and revoked without prior notice if a legitimate business need cannot be confirmed.
*   Repeated non-compliance with access control standards will be escalated to the relevant team manager and may result in publishing permissions being suspended.

Access control is not a one-time setup. It is the ongoing responsibility of the Report Owner and Workspace Admin to ensure that access remains appropriate as team membership and business needs change.

## Data Source Specific Guidelines:

### SAP Datasphere:

SAP Datasphere is the primary enterprise data platform. The guidelines below cover the connection and consumption of data from Datasphere within Power BI.

#### Workspace access:

To request access to an existing SAP Datasphere workspace or to request a new workspace, please follow the procedure here:

**_New Workspace:_** Follow the instructions on this link [SAP Datasphere - Getting Started](https://lindegroup.sharepoint.com/sites/LEGBLITSystems/SitePages/SAP%20Business%20Backbone/SAP%20Datasphere/Articles/GettingStarted.aspx) or this tutorial video [Tutorial\_SAPDatasphere.mp4](https://lindegroup.sharepoint.com/:v:/r/sites/msteams_48df48/Shared%20Documents/General/90%20Getting%20Started%20-%20Videos/Tutorial_SAPDatasphere.mp4?csf=1&web=1&e=MLd3eP)

**_Existing Workspace:_** To request access to an existing SAP Datasphere workspace, open myID, navigate to New Request, and add the desired workspace to your cart.
Link: [One Identity Manager Web Portal](https://myid.linde.name/api/html/qer-app-portal/#/dashboard)

#### Connection method:

![]()SAP Datasphere connector needs to be installed using Software Center.

#### Power BI Data Gateway:

Every Power BI workspace that connects to on-premises data sources requires a Data Gateway to be configured. Without it, scheduled refreshes will not function. To request a gateway for your workspace, please contact: [powerbi.support@linde-le.com](mailto:powerbi.support@linde-le.com).

### Databricks:

#### Download pbix file from Databricks:

A pre-configured .pbix file can be downloaded directly from the Databricks workspace. This file comes with the data connection already set up, allowing you to open it in Power BI Desktop and begin working immediately without any manual configuration.

There are two ways to download the .pbix file from Databricks:

*   From SQL Warehouse: Navigate to SQL Warehouses in your Databricks workspace, open the relevant warehouse, and use the option to download the pre-configured .pbix file directly from there.
*   From the Catalogue: Navigate to the Databricks Catalogue, locate the relevant table or dataset, and download the pre-configured .pbix file from the dataset options available within the Catalogue view.

#### Connect via Power BI Desktop:

Open Power BI Desktop and navigate to Get Data > Azure Databricks. The details required to establish the are available under SQL Warehouses in your Databricks workspace. Select the relevant warehouse, copy the connection details, and paste them into the connector fields in Power BI.

### Excel / SharePoint:

*   Excel files hosted on SharePoint are acceptable for supplementary or reference data that is manually maintained.
*   If the same data exists in a system database, the Excel connection must be replaced with a proper database connection.
*   Excel exports pulled from any system are not permitted as a data source. If the required data is not yet accessible through an approved connection, raise a formal request with the Data Platform team to establish one.

## Quality & Assurance:

### Semantic Model Reuse:

Developers must prioritize reusing existing semantic models over creating new ones whenever a suitable model already exists. This ensures consistency across the platform, reduces duplication, and keeps the data landscape maintainable.

The target architecture is to have multiple reports built on top of the same semantic model, rather than creating a dedicated semantic model per report. This promotes a single source of truth and ensures that business logic and definitions remain consistent across all reports consuming the same data.

Reusing an existing semantic model also brings an additional governance benefit: any Row Level Security (RLS) already configured on that model is automatically inherited by the new report. This means data access restrictions are consistently enforced without requiring additional setup, reducing the risk of accidental data exposure.

To reuse a semantic model, developers must request access permissions directly from the model's owner before integrating it into their solution. To check whether a suitable model already exists, developers should consult the Data Catalogue or reach out to the Data Analytics Team for guidance. New semantic models should only be created when no existing model adequately covers the required domain or use case.

# **Frontend:**

## Requesting a Power BI Pro License

Publishing reports to shared workspaces in Power BI Service requires a Pro license. To request a license based on your use case, please follow the procedure outlined here:

Service Portal Link: [New LE Power BI Pro license - Service Portal](https://smax.linde.com/saw/ess/offeringPage/23381612?query=Power%20bi)
Power BI SharePoint Page: [Microsoft Power BI](https://lindegroup.sharepoint.com/:u:/r/sites/LEGBLITSystems/SitePages/Microsoft%20Power%20BI/Microsoft%20Power%20BI.aspx?csf=1&web=1&e=VqRVNN)

## Report Design and Layout

Every visual must serve a clear, stated purpose. If the reason for a visual cannot be explained in one sentence, it likely does not belong in the report.

### Page structure:

*   Page 1 is always the Summary or Overview page. It should provide a one-screen answer to the core business question.
*   Every page must carry a clear, descriptive title.
*   Reports should generally not exceed 8 pages. If more pages are needed, consider splitting the report into two focused reports.
*   The last page of every report must be the Info Page, which is already included in the organizational template. This page should contain definitions, metric explanations, data source references, and any assumptions made in the report. The info icon available in the template header must be linked to this page, so that users can navigate directly to it from any page in the report for context and clarification.

### Filters and slicers:

*   Slicers should be placed in a consistent location, rather than scattered across the canvas.
*   Every slicer must have a visible label.
*   Where the same filter applies to multiple pages, use sync slicers.
*   Any report-level filters applied through the filter pane must be documented in the report description in Power BI Service.

### Visuals:

*   Every visual must have a clear, business-oriented title that explains what the user is looking at (not just the metric name).
*   Titles should follow a consistent naming convention, e.g., “Sales by Region (Current Year)” instead of vague labels like “Chart 1” or “Sales Data.”
*   Maintain consistent color usage across the report (e.g., same color for the same category or KPI across all pages).
*   Data labels should be enabled only when they improve clarity and do not clutter the visual.
*   Ensure alignment and spacing between visuals are consistent to maintain a clean and professional layout.

## Quality Checks:

Before publishing any report, developers must validate that the data behaves as expected from a business logic perspective. It is not sufficient for a report to simply load without errors. The underlying data must be verified for correctness.

### Business Logic Validation:

Validation should be based on known business rules and expected outcomes. For example, in a finance balance sheet report, assets and liabilities must net to zero. Any discrepancy indicates a data issue that must be resolved prior to publishing. Developers should identify the equivalent business logic rules for their specific domain and use them as the basis for their quality checks.

### Validation Table

Developers should implement a validation table within the model. This is a dedicated table that loads only the rows flagged as problematic based on defined business rules. For example, negative sales values, missing required fields, or mismatched date logic. The validation table can be reviewed by the Report Owner prior to publication and retained as a lightweight audit trail of known data issues.

### Faulty Data

Whenever a developer or user encounters faulty or inconsistent data, it must be flagged immediately. This ensures that data issues are tracked, communicated to the responsible parties, and resolved in a timely manner before they impact business decisions.

No report should be published until all defined quality checks have been reviewed and passed.

## Publication and Workspace Management

*   Publish only to approved, named workspaces. Personal workspaces must not be used for organizational reports.
*   Publish only to approved, named workspaces. Personal workspaces must not be used for organizational reports. A report published to a personal workspace requires every viewer to hold a Power BI Pro license, which carries a cost. Reports published to an organizational workspace can be accessed by any user with Viewer access at no additional license cost.
*   New workspaces can be requested via [powerbi.support@linde-le.com](mailto:powerbi.support@linde-le.com)
    *   For more details: [Microsoft Power BI - Getting Started](https://lindegroup.sharepoint.com/sites/LEGBLITSystems/SitePages/Microsoft%20Power%20BI/Help/Getting%20Started.aspx)
*   Workspace naming follows the convention defined in the original documentation of Power BI.
    *   For more details: [Microsoft Power BI - Getting Started](https://lindegroup.sharepoint.com/sites/LEGBLITSystems/SitePages/Microsoft%20Power%20BI/Help/Getting%20Started.aspx)
*   Upon publication, complete the report description field in Power BI Service. It must include the report's purpose, the Report Owner's name, the data source(s) used, and the refresh schedule.
*   Assign a sensitivity label that matches the data classification of the report content (Public, Internal, or Confidential).

### Folder Structure:

Reports within a workspace must be organized into folders based on **use case**, with each use case folder containing a dedicated **Archive subfolder** for older versions.

![]()

### Data Refresh Frequency:

Scheduled refresh must be configured for every published report that uses live data / semi-live data.

Refresh frequency must be aligned with the actual update frequency of the source data. Scheduling a daily refresh for a dataset that is only updated at the source once a month serves no purpose and wastes shared capacity. To determine and monitor the correct refresh schedule, use one of the following approaches:

*   **Lineage View (Power BI Service):** Navigate to the workspace, open the Lineage view, and trace how your dataset connects to its upstream sources. This shows when upstream datasets are refreshed, allowing you to schedule your report refresh shortly after.
*   **Monitor (Power BI Service):** Use the Monitoring hub in Power BI Service to track the refresh history of your dataset, including success, failure, and duration. This helps you verify that refreshes are running as expected and identify any recurring issues.
*   **If no lineage is available:** Contact the owner of the source file or system to confirm how frequently the data is updated and align your refresh schedule accordingly.

Refresh failure alerts must be enabled and directed to both the Report Developer and the Workspace Admin.

Refreshes should be scheduled during off-peak hours where possible, to minimize impact on source systems and on the Power BI, capacity shared across the organization.

### Power BI App Registration

All the published reports in Linde must be registered at Linde plc. Report Inventory.

_Note: Reports that are not registered within one month of publication will be removed by IT. A warning email is issued in advance, giving the Report Owner the opportunity to register the report before it is deleted._

Registration Link: [Linde plc. Report Inventory](https://apps.powerapps.com/play/e/613585e3-8656-4fe7-960f-0ca2d2332bd2/a/9f053580-c455-4e4d-8a5f-39d1bbb0df7b?tenantId=1562f007-09a4-4fcb-936b-e79246571fc7&source=sharebutton&sourcetime=1775648181480)

## Access Control on Power BI Service:

*   Workspace roles must be assigned based on the principle of least privilege. The four available roles are:

**Role**

**What they can do**

**Admin**

Full control — manage workspace settings, add or remove members, publish, and delete content. Reserved for workspace owners only.

**Member**

Publish and update reports, manage workspace apps, and add Contributors. Cannot change workspace settings.

**Contributor**

Create, edit, and delete reports within the workspace. Cannot publish apps or manage access. Intended for active report developers.

**Viewer**

Read-only access to published content. Cannot edit any report or dataset. Assigned to all report consumers.

*   *   Once a report with RLS is published, the security groups must be assigned to the RLS roles defined in Power BI Desktop (refer to Section 2.1). This is done by navigating to the semantic model in Power BI Service, opening the Security settings, and mapping each role to the appropriate group.
        *   It is strongly recommended to use Exchange groups set up by IT rather than assigning individual names.
        *   Exchange groups are centrally managed by IT and automatically reflect team changes, meaning access stays accurate without requiring manual updates each time someone joins or leaves.
*   The same principle applies to workspace role assignments, use security or Exchange groups rather than assigning roles to individuals one by one.
*   Guest user access requires approval from the regional IT Security team.
*   Service accounts used for scheduled data refresh must be registered and documented with IT. They must not be shared with or used by individual users.

_Note: RLS defined in Desktop is only enforced in the Service for users assigned the Viewer role. Users with Admin, Member, or Contributor roles bypass RLS by default, as they have edit permissions on the dataset._

## Maintenance and Version Control

The Report Owner is responsible for initiating a review whenever:

*   Business logic or KPI definitions change
*   The underlying data source is modified or replaced
*   The report has not been formally reviewed in more than 6 months

Reports with no recorded activity will be flagged for decommissioning by the business side. A reminder email will be sent before any action is taken.

### Version Control on Local Machine:

*   Maintain date-wise backup folders on the local system to preserve a history of local changes.
*   The report template includes a dedicated page titled "Document Control" for logging version history directly within the .pbix file. This must be kept up to date with each significant change.
*   A Document Control Excel file is provided as a reference in the template. Make a copy of this file, update the data source connection to point to your own copy, and use it to maintain a revision log for your report.

Excel File: [Template\_DocumentControl.xlsx](https://lindegroup-my.sharepoint.com/:x:/r/personal/e6nc70_linde-le_com/Documents/Documents/Project_DA/Power%20BI_SOP/Template_DocumentControl.xlsx?d=w81aca79b110143ea878e601a70f9ad69&csf=1&web=1&e=RUwqdH)

*   Always take the latest published version of the .pbix file as the starting point for any new update or edit, then publish it again once changes are complete. Do not work from an older local copy.
*   The folder structure below illustrates how reports on the local machine should be organized. This example shows the structure inside a single dashboard folder. ![]()

### Version Control on Power BI Workspace:

*   Before publishing an updated report, the current published version must be moved to the designated Archive folder within the workspace.
*   Publishing a newer version to an existing workspace report will overwrite the previous one. Archiving the prior version first ensures a rollback point is available if the updated report contains errors or unintended changes.

### Change Control:

A material change is defined as any modification that affects business logic, data sources, access permissions, RLS roles, or the visual structure of a published report.

*   Material changes must be approved in writing by the Report Owner before being published. Email confirmation is acceptable.
*   Minor changes such as cosmetic or formatting adjustments do not require formal approval but must still be logged in the Document Control page within the .pbix file.
*   Every change, whether material or minor, must be recorded in the Document Control revision log with a description of what changed, who approved it, and the date of publication.
*   The latest published version of the report must always be used as the starting point for any change. Working from an older local copy is not permitted.

### Decommissioning

A report must be considered for decommissioning when any of the following criteria are met:

*   The report has had no recorded activity or views for more than 6 months.
*   The underlying data source has been decommissioned or replaced.
*   The business need the report was built for no longer exists.
*   The Report Owner is no longer with the organization and no successor has been assigned.

The decommissioning process must follow these steps:

*   **Step 1:** The Data Analytics Team or Report Owner identifies the report as a candidate for decommissioning and notifies all known consumers.
*   **Step 2:** A 30-day notice period is given before any action is taken, allowing users to raise objections or request reassignment of ownership.
*   **Step 3:** If no objection is raised, the report is moved to the Archive folder within the workspace and access is removed from all users except the Workspace Admin.
*   **Step 4:** The report is marked as decommissioned in the Linde plc. Report Inventory with the date of retirement and the reason.
*   **Step 5:** Archived reports are retained for a minimum of 12 months before permanent deletion, in case reinstatement is required.

The Report Owner must provide written sign-off confirming that the report is no longer needed before the decommissioning process is completed.

# **Audit, Review & Compliance Monitoring**

Power BI reports and workspaces are subject to periodic audits conducted by the Data Analytics Team to verify compliance with this SOP.

*   Audits will be conducted at minimum once per year, with spot checks performed at any time without prior notice.
*   Full audits will cover a representative sample of published reports across workspaces.
*   The following artifacts will be requested as standard audit evidence:
    *   **Workspace access lists:** Who has access and at what role level.
    *   **RLS configuration and test records:** Proof that RLS roles were tested before publishing.
    *   **Refresh logs:** Confirmation that scheduled refreshes are running successfully.
    *   **Owner approval records:** Written confirmation that the Report Owner signed off before publication.
*   Audit findings will be shared with the Report Developer and Report Owner within \_\_ business days of the audit.
*   Developers and Owners must agree on a remediation plan within 5 business days of receiving findings and complete all actions by the agreed deadline.
*   Unresolved findings beyond the deadline will be escalated to the relevant team manager.

# **Exceptions, Incidents & Deviations**

## Exceptions:

*   Exceptions to any Mandatory Control must be approved by the Data Analytics Team before publication and supported by written proof (e.g. email, Teams message, or ticket).

## Incidents:

*   If faulty or unauthorized data is found in a published report, it must be taken offline immediately and the relevant parties notified. Proof of notification (e.g. email or chat archive) is sufficient record.

## Deviations:

*   Emergency changes made outside the standard process must be retrospectively approved by the Report Owner. A saved email or message thread serves as valid confirmation.

# **Document Control**

**Revision**

**Date**

**Author**

**Change Summary**

00

April 2026

Data Analytics Team

Initial release

# **Power BI & Other Relevant Documentation :**

**Power BI Documentation**

**Access our Power BI SharePoint:**

[Microsoft Power BI](https://lindegroup.sharepoint.com/sites/LEGBLITSystems/SitePages/Microsoft%20Power%20BI/Microsoft%20Power%20BI.aspx?xsdata=MDV8MDJ8c3llZC5tdWhhbW1hZC5hdW4ucmF6YS56YWlkaUBsaW5kZS5jb218MzM2YjJhOTlmM2VhNDk0ODE0YzkwOGRlOTkzMTc3ZGJ8MTU2MmYwMDcwOWE0NGZjYjkzNmJlNzkyNDY1NzFmYzd8MHwwfDYzOTExNjYzNTI4NjA3NzM2NXxVbmtub3dufFRXRnBiR1pzYjNkOGV5SkZiWEIwZVUxaGNHa2lPblJ5ZFdVc0lsWWlPaUl3TGpBdU1EQXdNQ0lzSWxBaU9pSlhhVzR6TWlJc0lrRk9Jam9pVFdGcGJDSXNJbGRVSWpveWZRPT18MHx8fA%3d%3d&sdata=b2x3VGUwNjhOWE12K3RDZE1HQStpRFdKY2pnOVRBYnUwVVJ1dWc2Vllldz0%3d&clickparams=eyAiWC1BcHBOYW1lIiA6ICJNaWNyb3NvZnQgT3V0bG9vayIsICJYLUFwcFZlcnNpb24iIDogIjE2LjAuMTk3MjUuMjAxNzAiLCAiT1MiIDogIldpbmRvd3MiIH0%3D)

**Get started:**

[Microsoft Power BI - Getting Started](https://lindegroup.sharepoint.com/sites/LEGBLITSystems/SitePages/Microsoft%20Power%20BI/Help/Getting%20Started.aspx?xsdata=MDV8MDJ8c3llZC5tdWhhbW1hZC5hdW4ucmF6YS56YWlkaUBsaW5kZS5jb218MzM2YjJhOTlmM2VhNDk0ODE0YzkwOGRlOTkzMTc3ZGJ8MTU2MmYwMDcwOWE0NGZjYjkzNmJlNzkyNDY1NzFmYzd8MHwwfDYzOTExNjYzNTI4NjA5MTA3M3xVbmtub3dufFRXRnBiR1pzYjNkOGV5SkZiWEIwZVUxaGNHa2lPblJ5ZFdVc0lsWWlPaUl3TGpBdU1EQXdNQ0lzSWxBaU9pSlhhVzR6TWlJc0lrRk9Jam9pVFdGcGJDSXNJbGRVSWpveWZRPT18MHx8fA%3d%3d&sdata=c0QrbUZ5eVhpNmZPMWRSVlZyVzhvckxIZVlFaEhEaFAxNHZ2Nnc0MGxVdz0%3d&clickparams=eyAiWC1BcHBOYW1lIiA6ICJNaWNyb3NvZnQgT3V0bG9vayIsICJYLUFwcFZlcnNpb24iIDogIjE2LjAuMTk3MjUuMjAxNzAiLCAiT1MiIDogIldpbmRvd3MiIH0%3D)

**Other Relevant Documentation & Training**

**Type of Documentation**

**Usage**

**Hyperlink**

General Power BI Documentation

Good for looking up formulas or reading about functionalities

[Power BI documentation - Power BI | Microsoft Learn](https://learn.microsoft.com/en-us/power-bi/)

Global Power BI Community

if you are stuck, the chances are high that someone else faced the same issue --> Power Bi has a very big online community

[Power BI forums - Microsoft Fabric Community](https://community.fabric.microsoft.com/t5/Power-BI-forums/ct-p/powerbi)

Linde Power BI Community

If you want support or help form colleagues --> reach out via the power bi engage community

[Viva Engage](https://engage.cloud.microsoft/main/org/lindegroup.onmicrosoft.com/groups/eyJfdHlwZSI6Ikdyb3VwIiwiaWQiOiI1Mzg2Njk1NDc1MyJ9)

Online Training (certification PL300)

Free Power BI training is offered by Microsoft (working towards a certification PL300)

[Course PL-300T00-A: Design and manage analytics solutions using Power BI - Training | Microsoft Learn](https://learn.microsoft.com/en-us/training/courses/pl-300t00)

Training within Linde

Training within Linde on Power BI (via the Elevate platform)

[Power BI Data Analyst Associate (PL-300) Cert Prep: Advanced Reporting in Power BI](https://linde.csod.com/ui/lms-learning-details/app/course/f0ca7bbb-506e-5f41-a8a2-315ea0682514)

Free LinkedIn Learning training

Qualitative LinkedIn Learning training on Power BI

[Learning objectives | LinkedIn Learning](https://www.linkedin.com/learning/complete-guide-to-power-bi-for-data-analysts-by-microsoft-press/learning-objectives-20269078?u=325376250)

YouTube channel

YouTube channel with high quality content on all features, formulas and general content related to Power BI and DAX

[Guy in a Cube - YouTube](https://www.youtube.com/@GuyInACube)