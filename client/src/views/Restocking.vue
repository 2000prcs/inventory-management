<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div v-if="submitSuccess" class="success-banner">
        <span>{{ submitSuccess }}</span>
        <button type="button" class="dismiss-btn" @click="submitSuccess = null">&times;</button>
      </div>
      <div v-if="submitError" class="error">{{ submitError }}</div>

      <div class="card budget-card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budgetLabel') }}</h3>
          <div class="budget-amount">{{ formatCurrency(budget, currentCurrency) }}</div>
        </div>
        <input
          type="range"
          min="0"
          max="25000"
          step="500"
          v-model.number="budget"
          class="budget-slider"
        />
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.totalAllocated') }}</div>
          <div class="stat-value">{{ formatCurrencyWithDecimals(totalAllocated, currentCurrency, 2) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.remainingBudget') }}</div>
          <div class="stat-value">{{ formatCurrencyWithDecimals(remainingBudget, currentCurrency, 2) }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.itemsSelected') }}</div>
          <div class="stat-value">{{ fundedItems.length }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendations') }}</h3>
          <button
            type="button"
            class="place-order-btn"
            :disabled="!canSubmit"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.placingOrder') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="recommendations.length === 0" class="empty-state">
          {{ t('restocking.noRecommendations') }}
        </div>
        <template v-else>
          <div v-if="allItemsFunded" class="all-funded-banner">
            {{ t('restocking.allFunded') }}
          </div>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>{{ t('restocking.table.sku') }}</th>
                  <th>{{ t('restocking.table.itemName') }}</th>
                  <th>{{ t('restocking.table.demand') }}</th>
                  <th>{{ t('restocking.table.quantity') }}</th>
                  <th>{{ t('restocking.table.unitCost') }}</th>
                  <th>{{ t('restocking.table.lineTotal') }}</th>
                  <th>{{ t('restocking.table.leadTime') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in recommendations"
                  :key="item.item_sku"
                  :class="{ 'skipped-row': !item.funded }"
                >
                  <td><strong>{{ item.item_sku }}</strong></td>
                  <td>{{ item.item_name }}</td>
                  <td>{{ item.current_demand }} &rarr; {{ item.forecasted_demand }}</td>
                  <td>
                    <span v-if="item.funded">{{ item.quantity }}</span>
                    <span v-else class="skipped-reason">{{ t('restocking.skippedReason') }}</span>
                  </td>
                  <td>{{ formatCurrencyWithDecimals(item.unit_cost, currentCurrency, 2) }}</td>
                  <td>{{ formatCurrencyWithDecimals(item.lineTotal, currentCurrency, 2) }}</td>
                  <td>{{ t('orders.leadTimeDays', { count: item.lead_time_days }) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
// formatCurrency rounds to whole units - fine for the slider (step 500), but unit costs
// like PSU-501's $18.99 would render as "$19", so money columns use the 2-decimal variant
// to match how Inventory.vue prints unit_cost.
import { formatCurrency, formatCurrencyWithDecimals } from '../utils/currency'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency } = useI18n()

    const loading = ref(true)
    const error = ref(null)
    const allForecasts = ref([])

    // Start at 5000 so the page has funded + skipped rows on first load
    const budget = ref(5000)

    const submitting = ref(false)
    const submitSuccess = ref(null)
    const submitError = ref(null)

    const loadForecasts = async () => {
      try {
        loading.value = true
        error.value = null
        allForecasts.value = await api.getDemandForecasts()
      } catch (err) {
        error.value = 'Failed to load demand forecasts: ' + err.message
      } finally {
        loading.value = false
      }
    }

    // Greedy budget allocation:
    // 1. Only forecasts with a positive demand gap are eligible (drops MTR-304, whose
    //    forecasted demand is below current demand).
    // 2. Sort by gap descending, so the biggest shortfalls get first crack at the budget.
    // 3. Walk the sorted list tracking remaining budget. An item is only funded if its
    //    FULL quantity (gap) fits in what's left - no partial fills. If it doesn't fit,
    //    mark it skipped and keep walking (don't stop) - a later, cheaper item with a
    //    smaller line total can still be funded even though an earlier, pricier one was
    //    skipped.
    const recommendations = computed(() => {
      const eligible = allForecasts.value
        .map(f => ({ ...f, gap: f.forecasted_demand - f.current_demand }))
        .filter(f => f.gap > 0)
        .sort((a, b) => b.gap - a.gap)

      let remaining = budget.value
      const results = []

      for (const item of eligible) {
        const lineTotal = item.gap * item.unit_cost
        if (lineTotal <= remaining) {
          results.push({ ...item, funded: true, quantity: item.gap, lineTotal })
          remaining -= lineTotal
        } else {
          results.push({ ...item, funded: false, quantity: item.gap, lineTotal })
        }
      }

      return results
    })

    const fundedItems = computed(() => recommendations.value.filter(item => item.funded))

    const totalAllocated = computed(() =>
      fundedItems.value.reduce((sum, item) => sum + item.lineTotal, 0)
    )

    const remainingBudget = computed(() => budget.value - totalAllocated.value)

    const allItemsFunded = computed(() =>
      recommendations.value.length > 0 && recommendations.value.every(item => item.funded)
    )

    const canSubmit = computed(() => fundedItems.value.length > 0 && !submitting.value)

    const placeOrder = async () => {
      submitting.value = true
      submitError.value = null
      submitSuccess.value = null

      try {
        const payload = {
          budget: budget.value,
          items: fundedItems.value.map(item => ({
            sku: item.item_sku,
            name: item.item_name,
            quantity: item.quantity,
            unit_cost: item.unit_cost,
            lead_time_days: item.lead_time_days
          }))
        }

        const result = await api.createRestockOrder(payload)
        submitSuccess.value = t('restocking.orderSuccess', { orderNumber: result.order_number })
      } catch (err) {
        submitError.value = `${t('restocking.orderError')}: ${err.message}`
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadForecasts)

    return {
      t,
      currentCurrency,
      formatCurrency,
      formatCurrencyWithDecimals,
      loading,
      error,
      budget,
      recommendations,
      fundedItems,
      totalAllocated,
      remainingBudget,
      allItemsFunded,
      canSubmit,
      submitting,
      submitSuccess,
      submitError,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  padding-bottom: 1.5rem;
}

.budget-amount {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-text);
}

.budget-slider {
  width: 100%;
  height: 6px;
  border-radius: 999px;
  background: var(--color-border);
  appearance: none;
  -webkit-appearance: none;
  outline: none;
  cursor: pointer;
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--color-primary);
  border: 3px solid white;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.3);
  cursor: pointer;
}

.budget-slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--color-primary);
  border: 3px solid white;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.3);
  cursor: pointer;
}

.budget-slider::-moz-range-track {
  height: 6px;
  border-radius: 999px;
  background: var(--color-border);
}

.place-order-btn {
  background: var(--color-primary-dark);
  color: white;
  border: none;
  border-radius: 8px;
  padding: 0.5rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: var(--color-primary-darker);
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: var(--color-text-muted);
  font-size: 0.938rem;
}

.all-funded-banner {
  background: #d1fae5;
  color: #065f46;
  border: 1px solid #a7f3d0;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
  font-size: 0.875rem;
  font-weight: 600;
}

.success-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #d1fae5;
  border: 1px solid #a7f3d0;
  color: #065f46;
  padding: 0.875rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.938rem;
}

.dismiss-btn {
  background: none;
  border: none;
  color: #065f46;
  font-size: 1.25rem;
  line-height: 1;
  cursor: pointer;
  padding: 0 0.25rem;
}

.skipped-row {
  color: #94a3b8;
}

.skipped-row td {
  color: #94a3b8;
}

.skipped-reason {
  font-style: italic;
  font-size: 0.813rem;
  color: #94a3b8;
}
</style>
