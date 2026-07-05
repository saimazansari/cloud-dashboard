package main

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"strconv"
	"strings"
	"time"

	"github.com/Azure/azure-sdk-for-go/sdk/azidentity"
	"github.com/Azure/azure-sdk-for-go/sdk/resourcemanager/compute/armcompute"
	"github.com/Azure/azure-sdk-for-go/sdk/resourcemanager/costmanagement/armcostmanagement"
	"github.com/Azure/azure-sdk-for-go/sdk/resourcemanager/resourcegraph/armresourcegraph"
	"github.com/Azure/azure-sdk-for-go/sdk/resourcemanager/resources/armsubscriptions"
)

type AzureManager struct {
	subscriptionID string
	credential     *azidentity.DefaultAzureCredential
	resourceGraph  *armresourcegraph.Client
	vmClient       *armcompute.VirtualMachinesClient
}

type SubscriptionInfo struct {
	ID             string `json:"id"`
	DisplayName    string `json:"display_name"`
	State          string `json:"state"`
	IsCurrent      bool   `json:"is_current"`
}

func NewAzureManager(subscriptionID string) (*AzureManager, error) {
	cred, err := azidentity.NewDefaultAzureCredential(nil)
	if err != nil {
		return nil, fmt.Errorf("azure credential: %w", err)
	}

	rgClient, err := armresourcegraph.NewClient(cred, nil)
	if err != nil {
		return nil, fmt.Errorf("resource graph client: %w", err)
	}

	vmClient, err := armcompute.NewVirtualMachinesClient(subscriptionID, cred, nil)
	if err != nil {
		return nil, fmt.Errorf("vm client: %w", err)
	}

	return &AzureManager{
		subscriptionID: subscriptionID,
		credential:     cred,
		resourceGraph:  rgClient,
		vmClient:       vmClient,
	}, nil
}

func (a *AzureManager) ListSubscriptions(ctx context.Context) ([]SubscriptionInfo, error) {
	subClient, err := armsubscriptions.NewClient(a.credential, nil)
	if err != nil {
		return nil, fmt.Errorf("subscriptions client: %w", err)
	}

	pager := subClient.NewListPager(nil)
	var subs []SubscriptionInfo
	for pager.More() {
		page, err := pager.NextPage(ctx)
		if err != nil {
			return nil, fmt.Errorf("list subscriptions: %w", err)
		}
		for _, s := range page.Value {
			if s == nil {
				continue
			}
			id := ""
			if s.SubscriptionID != nil {
				id = *s.SubscriptionID
			}
			name := id
			if s.DisplayName != nil {
				name = *s.DisplayName
			}
			state := ""
			if s.State != nil {
				state = string(*s.State)
			}
			subs = append(subs, SubscriptionInfo{
				ID:          id,
				DisplayName: name,
				State:       state,
				IsCurrent:   id == a.subscriptionID,
			})
		}
	}

	if subs == nil {
		subs = []SubscriptionInfo{}
	}
	return subs, nil
}

var azureTypeMap = map[string]string{
	"microsoft.compute/virtualmachines":          "Virtual Machine",
	"microsoft.storage/storageaccounts":          "Storage Account",
	"microsoft.network/loadbalancers":            "Load Balancer",
	"microsoft.sql/servers/databases":            "Database",
	"microsoft.sql/servers":                      "Database",
	"microsoft.containerservice/managedclusters":  "Kubernetes Cluster",
	"microsoft.web/sites":                        "Serverless Function",
	"microsoft.cdn/profiles":                     "CDN Profile",
	"microsoft.network/virtualnetworks":          "Virtual Network",
	"microsoft.network/publicipaddresses":        "Public IP",
	"microsoft.network/networkinterfaces":        "Network Interface",
	"microsoft.network/networksecuritygroups":    "Network Security Group",
	"microsoft.keyvault/vaults":                  "Key Vault",
	"microsoft.operationalinsights/workspaces":   "Log Analytics",
	"microsoft.containerregistry/registries":     "Container Registry",
	"microsoft.compute/disks":                    "Managed Disk",
}

func mapAzureType(azureType string) string {
	lower := strings.ToLower(azureType)
	if t, ok := azureTypeMap[lower]; ok {
		return t
	}
	parts := strings.Split(azureType, "/")
	return parts[len(parts)-1]
}

type azureResourceResult struct {
	ID            string                 `json:"id"`
	Name          string                 `json:"name"`
	Type          string                 `json:"type"`
	Location      string                 `json:"location"`
	ResourceGroup string                 `json:"resourceGroup"`
	Tags          map[string]interface{} `json:"tags,omitempty"`
	Properties    map[string]interface{} `json:"properties,omitempty"`
	Sku           map[string]interface{} `json:"sku,omitempty"`
}

func (a *AzureManager) getVMStatus(ctx context.Context, resourceGroup, vmName string) string {
	instanceView, err := a.vmClient.InstanceView(ctx, resourceGroup, vmName, nil)
	if err != nil {
		return "unknown"
	}
	if instanceView.Statuses == nil {
		return "unknown"
	}
	for _, status := range instanceView.Statuses {
		if status.Code == nil {
			continue
		}
		code := *status.Code
		if strings.HasPrefix(code, "PowerState/") {
			switch {
			case strings.HasSuffix(code, "running"):
				return "running"
			case strings.HasSuffix(code, "stopped"):
				return "stopped"
			case strings.HasSuffix(code, "deallocated"):
				return "stopped"
			default:
				return "running"
			}
		}
	}
	return "running"
}

func (a *AzureManager) resourceStatus(azureType, provisioningState string) string {
	provisioningState = strings.ToLower(provisioningState)
	switch {
	case provisioningState == "" || provisioningState == "succeeded":
		return "running"
	case provisioningState == "running" || provisioningState == "updating":
		return "running"
	case provisioningState == "stopped" || provisioningState == "deallocated":
		return "stopped"
	case provisioningState == "deleting" || provisioningState == "deleted":
		return "terminated"
	case provisioningState == "failed":
		return "terminated"
	default:
		return "running"
	}
}

func extractProvisioningState(props map[string]interface{}) string {
	if props == nil {
		return ""
	}
	if ps, ok := props["provisioningState"].(string); ok {
		return ps
	}
	return ""
}

func extractSku(sku map[string]interface{}, props map[string]interface{}) string {
	if sku != nil {
		if name, ok := sku["name"].(string); ok {
			return name
		}
		if name, ok := sku["Name"].(string); ok {
			return name
		}
	}
	if props != nil {
		if s, ok := props["sku"]; ok {
			if m, ok := s.(map[string]interface{}); ok {
				if name, ok := m["name"].(string); ok {
					return name
				}
			}
		}
		if s, ok := props["skuName"].(string); ok {
			return s
		}
	}
	return ""
}

func parseTags(azureTags map[string]interface{}) map[string]string {
	tags := make(map[string]string)
	for k, v := range azureTags {
		if s, ok := v.(string); ok {
			tags[k] = s
		} else {
			tags[k] = fmt.Sprintf("%v", v)
		}
	}
	return tags
}

func (a *AzureManager) ListResources(ctx context.Context) ([]Resource, error) {
	query := fmt.Sprintf(
		`resources | where subscriptionId == '%s' | project id, name, type, location, resourceGroup, tags, properties, sku`,
		a.subscriptionID,
	)

	req := armresourcegraph.QueryRequest{
		Query:         &query,
		Subscriptions: []*string{&a.subscriptionID},
	}

	rgCtx, rgCancel := context.WithTimeout(ctx, 20*time.Second)
	defer rgCancel()

	result, err := a.resourceGraph.Resources(rgCtx, req, nil)
	if err != nil {
		return nil, fmt.Errorf("resource graph query: %w", err)
	}

	jsonData, err := json.Marshal(result.QueryResponse.Data)
	if err != nil {
		return nil, fmt.Errorf("marshal resource graph data: %w", err)
	}

	var azureResources []azureResourceResult
	if err := json.Unmarshal(jsonData, &azureResources); err != nil {
		return nil, fmt.Errorf("unmarshal resource graph data: %w", err)
	}

	var resources []Resource
	for i, ar := range azureResources {
		rType := mapAzureType(ar.Type)
		status := a.resourceStatus(rType, extractProvisioningState(ar.Properties))

		if strings.ToLower(ar.Type) == "microsoft.compute/virtualmachines" {
			vmCtx, vmCancel := context.WithTimeout(ctx, 5*time.Second)
			status = a.getVMStatus(vmCtx, ar.ResourceGroup, ar.Name)
			vmCancel()
		}

		now := time.Now()
		r := Resource{
			ID:             i + 1,
			UserID:         0,
			Name:           ar.Name,
			Type:           rType,
			Region:         ar.Location,
			CostPerHour:    costPerHour(rType),
			Status:         status,
			Tags:           parseTags(ar.Tags),
			CreatedAt:      now,
			UpdatedAt:      now,
			ResourceGroup:  ar.ResourceGroup,
			SubscriptionID: a.subscriptionID,
			Sku:            extractSku(ar.Sku, ar.Properties),
		}
		r.Tags["_azure_id"] = ar.ID
		r.Tags["_resource_group"] = ar.ResourceGroup
		resources = append(resources, r)
	}

	if resources == nil {
		resources = []Resource{}
	}
	return resources, nil
}

func (a *AzureManager) GetResource(ctx context.Context, resourceID string) (Resource, error) {
	resources, err := a.ListResources(ctx)
	if err != nil {
		return Resource{}, err
	}
	idNum, err := strconv.Atoi(resourceID)
	if err != nil {
		return Resource{}, fmt.Errorf("invalid resource id: %s", resourceID)
	}
	for _, r := range resources {
		if r.ID == idNum {
			return r, nil
		}
	}
	return Resource{}, fmt.Errorf("resource not found: %s", resourceID)
}

func (a *AzureManager) StopResource(ctx context.Context, resourceID string) error {
	parts := strings.Split(resourceID, "/")
	if len(parts) < 9 {
		return fmt.Errorf("invalid ARM ID: %s", resourceID)
	}
	resourceGroup := parts[4]
	resourceName := parts[len(parts)-1]

	poller, err := a.vmClient.BeginDeallocate(ctx, resourceGroup, resourceName, nil)
	if err != nil {
		return fmt.Errorf("deallocate VM: %w", err)
	}
	_, err = poller.PollUntilDone(ctx, nil)
	return err
}

func (a *AzureManager) StartResource(ctx context.Context, resourceID string) error {
	parts := strings.Split(resourceID, "/")
	if len(parts) < 9 {
		return fmt.Errorf("invalid ARM ID: %s", resourceID)
	}
	resourceGroup := parts[4]
	resourceName := parts[len(parts)-1]

	poller, err := a.vmClient.BeginStart(ctx, resourceGroup, resourceName, nil)
	if err != nil {
		return fmt.Errorf("start VM: %w", err)
	}
	_, err = poller.PollUntilDone(ctx, nil)
	return err
}

func (a *AzureManager) DeleteResource(ctx context.Context, resourceID string) error {
	parts := strings.Split(resourceID, "/")
	if len(parts) < 9 {
		return fmt.Errorf("invalid ARM ID: %s", resourceID)
	}
	resourceGroup := parts[4]
	resourceName := parts[len(parts)-1]

	poller, err := a.vmClient.BeginDelete(ctx, resourceGroup, resourceName, nil)
	if err != nil {
		return fmt.Errorf("delete VM: %w", err)
	}
	_, err = poller.PollUntilDone(ctx, nil)
	return err
}

func (a *AzureManager) GetCostSummary(ctx context.Context) (CostSummary, error) {
	resources, err := a.ListResources(ctx)
	if err != nil {
		return CostSummary{}, err
	}

	costResult, err := a.queryCost(ctx)
	if err != nil {
		return a.computeCostSummaryFallback(resources), nil
	}

	return a.parseCostResult(costResult, resources)
}

func (a *AzureManager) queryCost(ctx context.Context) (*armcostmanagement.QueryClientUsageResponse, error) {
	qCtx, qCancel := context.WithTimeout(ctx, 30*time.Second)
	defer qCancel()

	endDate := time.Now()
	startDate := endDate.AddDate(0, 0, -30)
	scope := fmt.Sprintf("/subscriptions/%s", a.subscriptionID)

	timeframe := armcostmanagement.TimeframeTypeCustom
	query := armcostmanagement.QueryDefinition{
		Type:      toPtr(armcostmanagement.ExportTypeActualCost),
		Timeframe: &timeframe,
		TimePeriod: &armcostmanagement.QueryTimePeriod{
			From: &startDate,
			To:   &endDate,
		},
		Dataset: &armcostmanagement.QueryDataset{
			Granularity: toPtr(armcostmanagement.GranularityTypeDaily),
			Aggregation: map[string]*armcostmanagement.QueryAggregation{
				"totalCost": {
					Name:     toPtr("PreTaxCost"),
					Function: toPtr(armcostmanagement.FunctionTypeSum),
				},
			},
		},
	}

	costClient, err := armcostmanagement.NewQueryClient(a.credential, nil)
	if err != nil {
		return nil, err
	}

	result, err := costClient.Usage(qCtx, scope, query, nil)
	if err != nil {
		return nil, err
	}
	return &result, nil
}

func (a *AzureManager) computeCostSummaryFallback(resources []Resource) CostSummary {
	var summary CostSummary
	byType := make(map[string]*CostByType)

	for _, r := range resources {
		monthly := r.CostPerHour * 730
		summary.TotalHourly += r.CostPerHour
		summary.TotalMonthly += monthly

		entry := ResourceWithCost{Resource: r, MonthlyCost: monthly}
		summary.Resources = append(summary.Resources, entry)

		if _, ok := byType[r.Type]; !ok {
			byType[r.Type] = &CostByType{Type: r.Type}
		}
		byType[r.Type].Count++
		byType[r.Type].TotalHourly += r.CostPerHour
		byType[r.Type].TotalMonthly += monthly
	}

	for _, bt := range byType {
		summary.ByType = append(summary.ByType, *bt)
	}
	return summary
}

func (a *AzureManager) parseCostResult(result *armcostmanagement.QueryClientUsageResponse, resources []Resource) (CostSummary, error) {
	rows := result.QueryResult.Properties.Rows
	if rows == nil || len(rows) == 0 {
		return a.computeCostSummaryFallback(resources), nil
	}

	costByType := make(map[string]float64)
	var totalCost float64

	for _, row := range rows {
		if len(row) < 3 {
			continue
		}
		rType, ok := row[0].(string)
		if !ok {
			continue
		}
		cost, ok := row[1].(float64)
		if !ok {
			continue
		}
		costByType[mapAzureType(rType)] += cost
		totalCost += cost
	}

	totalHourly := totalCost / 30.0 / 24.0
	var summary CostSummary
	summary.TotalHourly = math.Round(totalHourly*100) / 100
	summary.TotalMonthly = math.Round(totalCost/30.0*730*100) / 100

	typeCount := make(map[string]int)
	for _, r := range resources {
		typeCount[r.Type]++
	}

	for _, r := range resources {
		monthly := r.CostPerHour * 730
		entry := ResourceWithCost{Resource: r, MonthlyCost: monthly}
		summary.Resources = append(summary.Resources, entry)
	}

	for _, mappedType := range azureTypeMap {
		if c, ok := costByType[mappedType]; ok && c > 0 {
			monthly := c / 30.0 * 730.0
			hourly := c / 30.0 / 24.0
			summary.ByType = append(summary.ByType, CostByType{
				Type:         mappedType,
				Count:        typeCount[mappedType],
				TotalHourly:  math.Round(hourly*100) / 100,
				TotalMonthly: math.Round(monthly*100) / 100,
			})
		}
	}

	if len(summary.ByType) == 0 {
		return a.computeCostSummaryFallback(resources), nil
	}
	return summary, nil
}

func (a *AzureManager) GetCostHistory(ctx context.Context) ([]CostEntry, error) {
	result, err := a.queryCost(ctx)
	if err != nil {
		return a.seedCostHistoryFallback(), nil
	}

	rows := result.QueryResult.Properties.Rows
	if rows == nil || len(rows) == 0 {
		return a.seedCostHistoryFallback(), nil
	}

	var entries []CostEntry
	for _, row := range rows {
		if len(row) < 3 {
			continue
		}
		dateRaw, ok := row[2].(string)
		if !ok || len(dateRaw) < 10 {
			continue
		}
		cost, ok := row[1].(float64)
		if !ok {
			continue
		}
		entries = append(entries, CostEntry{
			Date:      dateRaw[:10],
			TotalCost: math.Round(cost*100) / 100,
		})
	}

	if len(entries) == 0 {
		return a.seedCostHistoryFallback(), nil
	}
	return entries, nil
}

func (a *AzureManager) seedCostHistoryFallback() []CostEntry {
	var entries []CostEntry
	now := time.Now()
	baseHourly := 0.15
	for i := 29; i >= 0; i-- {
		date := now.AddDate(0, 0, -i)
		hourly := baseHourly * (0.8 + float64(i%5)*0.05)
		entries = append(entries, CostEntry{
			Date:      date.Format("2006-01-02"),
			TotalCost: math.Round(hourly*24*100) / 100,
		})
	}
	return entries
}

func (a *AzureManager) BatchAction(ctx context.Context, action string, resources []Resource) error {
	for _, r := range resources {
		azID := r.Tags["_azure_id"]
		if azID == "" {
			continue
		}
		switch action {
		case "stop":
			if err := a.StopResource(ctx, azID); err != nil {
				return err
			}
		case "start":
			if err := a.StartResource(ctx, azID); err != nil {
				return err
			}
		case "terminate":
			if err := a.StopResource(ctx, azID); err != nil {
				return err
			}
		case "delete":
			if err := a.DeleteResource(ctx, azID); err != nil {
				return err
			}
		}
	}
	return nil
}

func toPtr[T any](v T) *T {
	return &v
}
