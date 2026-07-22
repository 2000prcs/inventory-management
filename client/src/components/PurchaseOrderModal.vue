<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen && backlogItem" class="modal-overlay" @click="close">
        <div class="modal-container" @click.stop>
          <div class="modal-header">
            <h3 class="modal-title">{{ mode === 'create' ? t('purchaseOrder.createTitle') : t('purchaseOrder.viewTitle') }}</h3>
            <button class="close-button" @click="close">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <div class="context-header">
              <div class="context-title-section">
                <h4 class="item-name">{{ translateProductName(backlogItem.item_name) }}</h4>
                <div class="item-sku">{{ t('purchaseOrder.sku') }}: {{ backlogItem.item_sku }}</div>
              </div>
              <div class="shortage-badge">
                {{ shortage }} {{ t('dashboard.inventoryShortages.unitsShort') }}
              </div>
            </div>

            <!-- Create mode -->
            <form v-if="mode === 'create'" class="po-form" @submit.prevent="handleSubmit">
              <div v-if="submitError" class="form-error">{{ submitError }}</div>

              <div class="form-group">
                <label class="form-label">{{ t('purchaseOrder.supplier') }}</label>
                <input
                  v-model="supplierName"
                  type="text"
                  class="form-input"
                  :placeholder="t('purchaseOrder.supplierPlaceholder')"
                />
              </div>

              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">{{ t('purchaseOrder.quantity') }}</label>
                  <input
                    v-model.number="quantity"
                    type="number"
                    min="1"
                    class="form-input"
                  />
                </div>

                <div class="form-group">
                  <label class="form-label">{{ t('purchaseOrder.unitCost') }}</label>
                  <input
                    v-model.number="unitCost"
                    type="number"
                    min="0"
                    step="0.01"
                    class="form-input"
                  />
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">{{ t('purchaseOrder.expectedDelivery') }}</label>
                <input
                  v-model="expectedDeliveryDate"
                  type="date"
                  class="form-input"
                />
              </div>

              <div class="form-group">
                <label class="form-label">{{ t('purchaseOrder.notes') }}</label>
                <textarea
                  v-model="notes"
                  class="form-textarea"
                  rows="3"
                  :placeholder="t('purchaseOrder.notesPlaceholder')"
                ></textarea>
              </div>

              <div class="total-cost-line">
                <span class="total-cost-label">{{ t('purchaseOrder.totalCost') }}</span>
                <span class="total-cost-value">{{ formatCurrencyWithDecimals(totalCost, currentCurrency, 2) }}</span>
              </div>
            </form>

            <!-- View mode -->
            <div v-else class="po-view">
              <div v-if="viewLoading" class="loading">{{ t('common.loading') }}</div>
              <div v-else-if="viewError" class="error">{{ viewError }}</div>
              <div v-else-if="purchaseOrder" class="info-grid">
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.supplier') }}</div>
                  <div class="info-value">{{ purchaseOrder.supplier_name }}</div>
                </div>

                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.status') }}</div>
                  <div class="info-value">
                    <span class="badge status">{{ purchaseOrder.status }}</span>
                  </div>
                </div>

                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.quantity') }}</div>
                  <div class="info-value">{{ purchaseOrder.quantity }}</div>
                </div>

                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.unitCost') }}</div>
                  <div class="info-value">{{ formatCurrencyWithDecimals(purchaseOrder.unit_cost, currentCurrency, 2) }}</div>
                </div>

                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.totalCost') }}</div>
                  <div class="info-value">{{ formatCurrencyWithDecimals(viewTotalCost, currentCurrency, 2) }}</div>
                </div>

                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.expectedDelivery') }}</div>
                  <div class="info-value">{{ formatDate(purchaseOrder.expected_delivery_date) }}</div>
                </div>

                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.createdDate') }}</div>
                  <div class="info-value">{{ formatDate(purchaseOrder.created_date) }}</div>
                </div>

                <div v-if="purchaseOrder.notes" class="info-item info-item-wide">
                  <div class="info-label">{{ t('purchaseOrder.notes') }}</div>
                  <div class="info-value">{{ purchaseOrder.notes }}</div>
                </div>
              </div>
            </div>
          </div>

          <div class="modal-footer">
            <button v-if="mode === 'create'" class="btn-secondary" @click="close">{{ t('purchaseOrder.cancel') }}</button>
            <button v-if="mode === 'create'" class="btn-primary" :disabled="submitting" @click="handleSubmit">
              {{ submitting ? t('purchaseOrder.submitting') : t('purchaseOrder.submit') }}
            </button>
            <button v-if="mode === 'view'" class="btn-secondary" @click="close">{{ t('purchaseOrder.close') }}</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrencyWithDecimals } from '../utils/currency'

const { t, currentCurrency, currentLocale, translateProductName } = useI18n()

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  },
  backlogItem: {
    type: Object,
    default: null
  },
  mode: {
    type: String,
    default: 'create'
  }
})

const emit = defineEmits(['close', 'po-created'])

const shortage = computed(() => {
  if (!props.backlogItem) return 0
  return props.backlogItem.quantity_needed - props.backlogItem.quantity_available
})

// Create-mode form state
const supplierName = ref('')
const quantity = ref(0)
const unitCost = ref(0)
const expectedDeliveryDate = ref('')
const notes = ref('')
const submitting = ref(false)
const submitError = ref(null)

const totalCost = computed(() => {
  const q = Number(quantity.value) || 0
  const c = Number(unitCost.value) || 0
  return q * c
})

// View-mode state
const viewLoading = ref(false)
const viewError = ref(null)
const purchaseOrder = ref(null)

const viewTotalCost = computed(() => {
  if (!purchaseOrder.value) return 0
  return purchaseOrder.value.quantity * purchaseOrder.value.unit_cost
})

const resetForm = () => {
  supplierName.value = ''
  quantity.value = shortage.value > 0 ? shortage.value : 0
  unitCost.value = 0
  expectedDeliveryDate.value = ''
  notes.value = ''
  submitError.value = null
  submitting.value = false
}

const fetchPurchaseOrder = async () => {
  if (!props.backlogItem) return
  viewLoading.value = true
  viewError.value = null
  purchaseOrder.value = null
  try {
    purchaseOrder.value = await api.getPurchaseOrderByBacklogItem(props.backlogItem.id)
  } catch (err) {
    viewError.value = t('purchaseOrder.loadError')
    console.error('Failed to load purchase order:', err)
  } finally {
    viewLoading.value = false
  }
}

// Re-initialize the form/view data whenever the modal is (re)opened, since the
// same instance is reused for every backlog item on the Dashboard.
watch(() => [props.isOpen, props.mode, props.backlogItem], ([open]) => {
  if (!open) return
  if (props.mode === 'create') {
    resetForm()
  } else {
    fetchPurchaseOrder()
  }
}, { immediate: true })

const handleSubmit = async () => {
  submitError.value = null

  if (!supplierName.value.trim() || !quantity.value || Number(quantity.value) <= 0 || !expectedDeliveryDate.value) {
    submitError.value = t('purchaseOrder.requiredFields')
    return
  }

  submitting.value = true
  try {
    const po = await api.createPurchaseOrder({
      backlog_item_id: props.backlogItem.id,
      supplier_name: supplierName.value.trim(),
      quantity: Number(quantity.value),
      unit_cost: Number(unitCost.value) || 0,
      expected_delivery_date: expectedDeliveryDate.value,
      notes: notes.value.trim() || null
    })
    emit('po-created', po)
  } catch (err) {
    submitError.value = err.response?.data?.detail || t('purchaseOrder.createError')
    console.error('Failed to create purchase order:', err)
  } finally {
    submitting.value = false
  }
}

const close = () => {
  emit('close')
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  const date = new Date(dateString)
  if (isNaN(date.getTime())) return '-'
  const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
  return date.toLocaleDateString(locale, {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
}

.modal-container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.close-button {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.close-button:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
}

.context-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid #e2e8f0;
  margin-bottom: 1.5rem;
}

.context-title-section {
  flex: 1;
  min-width: 0;
}

.item-name {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 0.375rem 0;
}

.item-sku {
  font-size: 0.875rem;
  color: #64748b;
  font-family: 'Monaco', 'Courier New', monospace;
}

.shortage-badge {
  flex-shrink: 0;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-size: 0.813rem;
  font-weight: 700;
  background: #fecaca;
  color: #991b1b;
  white-space: nowrap;
}

.po-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-error {
  padding: 0.75rem 1rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 500;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-label {
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.form-input,
.form-textarea {
  padding: 0.625rem 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.938rem;
  color: #0f172a;
  font-family: inherit;
  transition: border-color 0.15s ease;
}

.form-input:focus,
.form-textarea:focus {
  outline: none;
  border-color: #3b82f6;
}

.form-textarea {
  resize: vertical;
}

.total-cost-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  background: #eff6ff;
  border: 1px solid #93c5fd;
  border-radius: 10px;
}

.total-cost-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #1e40af;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.total-cost-value {
  font-size: 1.375rem;
  font-weight: 700;
  color: #0f172a;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
}

.info-item-wide {
  grid-column: 1 / -1;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.info-label {
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.info-value {
  font-size: 0.938rem;
  color: #0f172a;
  font-weight: 500;
}

.badge.status {
  display: inline-block;
  padding: 0.25rem 0.625rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  background: #fef3c7;
  color: #92400e;
}

.loading,
.error {
  padding: 2rem;
  text-align: center;
  color: #64748b;
}

.error {
  color: #dc2626;
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.btn-secondary {
  padding: 0.625rem 1.25rem;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.875rem;
  color: #334155;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.btn-secondary:hover {
  background: #e2e8f0;
  border-color: #cbd5e1;
}

.btn-primary {
  padding: 0.625rem 1.25rem;
  background: #3b82f6;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.875rem;
  color: white;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-primary:disabled {
  background: #93c5fd;
  cursor: not-allowed;
}

/* Modal transition animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95);
}
</style>
