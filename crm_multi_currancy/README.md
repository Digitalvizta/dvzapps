---

## **CRM Multi-Currency Module for Odoo**  

### **📌 Overview**  
The **CRM Multi-Currency** module enhances Odoo's CRM functionality by introducing multi-currency support for expected revenue. This allows businesses dealing in multiple currencies to track and convert potential revenue accurately.  

---

## **🚀 Key Features**  

### **1️⃣ Multi-Currency Support for Expected Revenue**  
- Adds a **"From Currency"** field (Many2one) to select the currency in which the expected revenue is recorded.  
- Adds a **"To Currency"** field (Many2one, always set to EUR, non-editable).  
- Adds an **"Expected Revenue"** field where users can enter the amount in the selected **From Currency**.  
- Adds a **"Converted Revenue (EUR)"** field to display the real-time converted revenue amount in EUR.  
- Automatically converts **expected revenue** from the source currency to EUR based on real-time exchange rates.  

### **2️⃣ Automatic Revenue Conversion**  
- Computes the **Converted Revenue (EUR)** dynamically using Odoo’s built-in currency conversion methods.  
- Uses the **current exchange rate** for accurate financial projections.  
- Ensures consistency by linking conversion to the company’s currency settings.  

### **3️⃣ List & Kanban View Enhancements**  
- Displays the following fields in the **List View**:  
  ✅ **From Currency**  
  ✅ **Expected Revenue**  
  ✅ **To Currency (EUR - Non-editable)**  
  ✅ **Converted Revenue (EUR)**  
- Ensures **"To Currency"** is not selectable and remains consistent across views.  

### **4️⃣ Enable Multi-Currency in Accounting**  
- **Prerequisite:** Before using this module, **Multi-Currency must be enabled in Accounting**:  
  1. Navigate to **Accounting → Settings**.  
  2. Enable **Multi-Currency**.  
  3. Set **EUR** as the default company currency if applicable.  

### **5️⃣ Seamless Integration with Odoo CRM**  
- Works natively within Odoo’s **CRM module** without disrupting existing workflows.  
- Fully compatible with **Odoo’s built-in currency management**.  
- Supports multi-company setups by adapting to the active company’s currency settings.  

---

## **🔧 Installation & Configuration**  

### **📥 Installation Steps**  
1. Copy this module into your Odoo **addons directory**.  
2. Restart the Odoo server:  
   ```sh
   odoo-bin -c /etc/odoo.conf -u crm_multi_currency
   ```
3. Activate the module from **Apps → CRM Multi-Currency**.  

### **🛠 Configuration**  
1. Navigate to **CRM → Leads**.  
2. Ensure that **Multi-Currency** is enabled in **Accounting → Settings**.  
3. Expected revenue will now be converted automatically.  

---

## **📝 Technical Details**  

### **🗃️ Models Used:**  
- **`crm.lead`** (Extended)  
  - `from_currency_id` → Many2one field for source currency.  
  - `expected_revenue` → Monetary field in **From Currency**.  
  - `to_currency_id` → Many2one field for target currency (always EUR, readonly).  
  - `converted_amount_eur` → Monetary field for converted revenue in EUR.  

### **⚙️ Business Logic:**  
- `_compute_converted_amount()` → Uses `from_currency_id._convert()` to calculate the **Converted Revenue (EUR)** dynamically.  

---

## **📷 Screenshots**  
### **1️⃣ CRM Form View with Multi-Currency Fields**  
*(Add a screenshot of the CRM Lead form with currency fields.)*  

### **2️⃣ Kanban & List View with Multi-Currency Fields**  
*(Add a screenshot of the CRM Kanban & List view displaying currency-related fields.)*  

---

## **📩 Support & Contact**  
For support or customization, contact:  
📧 Email: support@digitalvizta.com
🌐 Website: digitalvizta.com

---

This version **adds:**  
✅ **"From Currency" field next to Expected Revenue**  
✅ **"To Currency" field (always EUR, non-editable)**  
✅ **"Converted Revenue (EUR)" field**  
✅ **List View fields update**  
✅ **Multi-Currency enablement as a prerequisite**  

Let me know if you need further refinements! 🚀😊