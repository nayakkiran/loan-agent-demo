import time
import streamlit as st

st.set_page_config(page_title="Meridian Bank · Agentic personal loan demo", page_icon="🏦", layout="wide")

fmt = lambda n: "₹{:,}".format(n)

# ---------- Synthetic cases (replace with BigQuery queries later) ----------
CASES = {
    "A": dict(label="Case A · Clean profile", name="Ananya Rao", ref="PL-2026-04811", age=31,
              emp="Infosys Ltd (Cat A)", svc="4 yrs 2 mths", amt=600000, mo=48, rate=12.5,
              purpose="Home renovation", inc=85000,
              steps=[
                ("Document Agent", "OCR + document classifier", "Unstructured",
                 [("Salary slips read", "3 of 3"), ("Net salary (avg)", "₹84,200"), ("Statement credits (avg)", "₹84,900")],
                 "Documents are legible and consistent. Declared income matches verified income within 1%.", 0),
                ("KYC Agent", "PAN verify (mock) · Aadhaar match (mock)", "External API",
                 [("PAN status", "Valid, name matches"), ("Address match", "Yes")],
                 "KYC complete. No mismatches.", 0),
                ("Bureau Agent", "CIBIL (mock) · Account aggregator (mock)", "External API",
                 [("CIBIL score", "782"), ("Active loans", "1 (₹8,000 EMI)"), ("Enquiries, last 90 days", "1"), ("Delinquency", "None in 36 months")],
                 "Strong repayment record. Existing obligation is ₹8,000 a month.", 0),
                ("Policy Agent", "Policy search over RBI circulars and credit policy", "Unstructured",
                 [("Min. bureau score", "700 (§4.1)"), ("Max. FOIR", "50% (§4.3)"), ("Max. ticket for Cat A", "₹15,00,000 (§4.5)")],
                 "Three clauses apply. Policy limits are loaded for assessment.", 0),
                ("Credit Assessment Agent", "BigQuery SQL on customer, accounts, loans, repayments", "Structured",
                 [("Salary credited in our bank", "12 of 12 months"), ("Proposed EMI", "₹15,950"), ("FOIR", "28.2%"), ("Avg. balance (6 mths)", "₹61,000")],
                 "FOIR of 28.2% is well within the 50% limit. Surplus cash flow supports the EMI.", 0),
                ("Risk Flag Agent", "Cross-source consistency rules", "All sources",
                 [("Income mismatch", "None"), ("Enquiry spike", "No"), ("Adverse news / fraud list", "Clear")],
                 "No risk flags raised.", 0)],
              verdict="Recommend approval", tone="success",
              sub="Approve ₹6,00,000 for 48 months at 12.5%. EMI ₹15,950.",
              why=[("CIBIL 782 is above the minimum of 700", "Policy §4.1 · CIBIL (mock)"),
                   ("FOIR 28.2% is below the 50% cap", "Policy §4.3 · Core banking + bureau"),
                   ("Verified income matches declared income within 1%", "Salary slips + bank statement"),
                   ("Amount is within the ₹15L limit for employer Cat A", "Policy §4.5"),
                   ("KYC verified per RBI KYC Master Direction", "RBI KYC Directions")],
              refer_msg="Our officer will contact you with next steps."),
    "B": dict(label="Case B · Needs judgment", name="Rohit Mehta", ref="PL-2026-04827", age=38,
              emp="Private firm (Cat C)", svc="1 yr 3 mths", amt=1000000, mo=60, rate=14,
              purpose="Debt consolidation and travel", inc=70000,
              steps=[
                ("Document Agent", "OCR + document classifier", "Unstructured",
                 [("Salary slips read", "3 of 3"), ("Net salary on slips", "₹70,000"), ("Statement credits (avg)", "₹52,000")],
                 "Salary slips show ₹70,000 but bank credits average ₹52,000. A 26% gap.", 1),
                ("KYC Agent", "PAN verify (mock) · Aadhaar match (mock)", "External API",
                 [("PAN status", "Valid, name matches"), ("Address match", "Yes")],
                 "KYC complete. No mismatches.", 0),
                ("Bureau Agent", "CIBIL (mock) · Account aggregator (mock)", "External API",
                 [("CIBIL score", "668"), ("Active loans", "3 (₹14,500 EMI)"), ("Enquiries, last 90 days", "5"), ("Delinquency", "1 × 30 days late, 8 mths ago")],
                 "Below the 700 threshold, with five recent enquiries and a recent late payment.", 1),
                ("Policy Agent", "Policy search over RBI circulars and credit policy", "Unstructured",
                 [("Min. bureau score", "700 (§4.1)"), ("Max. FOIR", "50% (§4.3)"), ("Referral rule", "Score 650–699 → senior credit (§4.7)")],
                 "Score falls in the referral band. Applicant cannot be auto-approved.", 1),
                ("Credit Assessment Agent", "BigQuery SQL on customer, accounts, loans, repayments", "Structured",
                 [("Proposed EMI", "₹23,270"), ("FOIR on declared income", "54.0%"), ("FOIR on verified income", "72.6%"), ("Salary credited in our bank", "4 of 12 months")],
                 "On verified income the FOIR is 72.6%, far above the 50% cap.", 1),
                ("Risk Flag Agent", "Cross-source consistency rules", "All sources",
                 [("Income mismatch", "26% (flag)"), ("Enquiry spike", "Yes (5 in 90 days)"), ("Adverse news / fraud list", "Clear")],
                 "Two flags raised: income inconsistency and credit-seeking behaviour.", 1)],
              verdict="Refer to senior credit. Do not approve as applied.", tone="warning",
              sub="Suggested counter-offer: ₹4,00,000 for 48 months at 14%. EMI ₹10,930, FOIR 48.9% on verified income.",
              why=[("FOIR 72.6% on verified income exceeds the 50% cap", "Policy §4.3 · Bank statement"),
                   ("CIBIL 668 is below 700 and in the referral band", "Policy §4.1, §4.7 · CIBIL (mock)"),
                   ("Declared income is 26% above bank credits", "Salary slips vs statement"),
                   ("Five enquiries in 90 days and one late payment", "CIBIL (mock)"),
                   ("The counter-offer brings FOIR under the cap", "Assessment Agent calculation")],
              refer_msg="We can offer ₹4,00,000 for 48 months at 14% (EMI ₹10,930). Our officer will contact you."),
}
STAGES = ["Apply", "Documents", "Verification", "Bureau & checks", "Policy & assessment",
          "Officer decision", "Sanction", "Disbursement"]


# ---------- State ----------
def state(k):
    return st.session_state.setdefault(f"s_{k}", dict(sub=False, prog=0, dec=None, dis=False))


def stage_of(s):
    if s["dec"] == "approve":
        return 8 if s["dis"] else 7
    if s["dec"]:
        return 6
    p = s["prog"]
    if p >= 6: return 5
    if p >= 5: return 4
    if p >= 3: return 3
    if p >= 1 or s["sub"]: return 2
    return 0


def tracker(n):
    cells = "".join(
        f"<div style='flex:1;min-width:90px;text-align:center;font-size:12px;padding:6px 2px;"
        f"border-top:4px solid {'#0e7c7b' if i < n else '#d9e0e7'};"
        f"{'font-weight:700;' if i == n else ''}opacity:{1 if i <= n else .55}'>{t}</div>"
        for i, t in enumerate(STAGES))
    st.markdown(f"<div style='display:flex;gap:4px;margin:8px 0 18px;overflow-x:auto'>{cells}</div>", unsafe_allow_html=True)


def summary(c):
    st.markdown(
        f"**Applicant** {c['name']}, {c['age']}  \n**Employer** {c['emp']} · {c['svc']}  \n"
        f"**Loan asked** {fmt(c['amt'])} over {c['mo']} months  \n**Purpose** {c['purpose']}  \n"
        f"**Declared income** {fmt(c['inc'])} a month  \n**Reference** {c['ref']}")


def step_card(step, container):
    agent, tools, src, pulled, finding, warn = step
    with container:
        st.markdown(f"**{agent}**  \n<small>Tools: {tools}</small>", unsafe_allow_html=True)
        st.caption(f"Data source: {src}")
        st.markdown("\n".join(f"- {k}: **{v}**" for k, v in pulled))
        (st.warning if warn else st.success)(finding)


# ---------- Sidebar ----------
st.sidebar.title("Meridian Bank")
st.sidebar.caption("Agentic personal loan approval · synthetic data")
view = st.sidebar.radio("View", ["Applicant", "Credit officer"])
ck = st.sidebar.radio("Applicant case", list(CASES), format_func=lambda k: CASES[k]["label"])
if st.sidebar.button("Reset demo"):
    for k in list(st.session_state):
        if k.startswith("s_"): del st.session_state[k]
    st.rerun()
c, s = CASES[ck], state(ck)
tracker(stage_of(s))

# ---------- Applicant view ----------
if view == "Applicant":
    st.header("Personal loan application")
    if not s["sub"]:
        summary(c)
        st.markdown("**Documents**")
        for d in ["Aadhaar (masked)", "PAN card", "Last 3 salary slips", "6-month bank statement"]:
            st.markdown(f"- {d} ✅ ready to upload")
        st.caption("Consent for bureau and account aggregator checks is captured on submit.")
        if st.button("Submit application", type="primary"):
            s["sub"] = True; st.rerun()
    else:
        if s["dec"] == "approve":
            st.success(f"Approved. Your sanction letter and Key Fact Statement for {fmt(c['amt'])} are ready.")
        elif s["dec"] == "refer":
            st.info(c["refer_msg"])
        elif s["dec"] == "reject":
            st.error("We are unable to offer this loan as applied.")
        elif s["prog"] >= 6:
            st.info("Our credit officer is reviewing your application.")
        else:
            st.info("We are checking your documents and credit history. This usually takes minutes, not days.")
        summary(c)

# ---------- Officer view ----------
else:
    st.header(f"Case file · {c['ref']}")
    left, right = st.columns(2)
    with left:
        summary(c)
        if not s["sub"]:
            if st.button("Mark application as received"):
                s["sub"] = True; st.rerun()
        elif s["prog"] == 0:
            run = st.button("Run agents", type="primary")
        else:
            run = False
    with right:
        st.subheader("Agent activity")
        holder = st.container()
        if s["sub"] and s["prog"] == 0 and run:
            for i, step in enumerate(c["steps"]):
                with st.spinner(f"{step[0]} working…"):
                    time.sleep(0.9)
                step_card(step, holder)
                s["prog"] = i + 1
            st.rerun()
        elif s["prog"] > 0:
            for step in c["steps"][: s["prog"]]:
                step_card(step, holder)
        else:
            st.caption("Agents have not started yet.")

    if s["prog"] >= 6:
        with left:
            st.divider()
            (st.success if c["tone"] == "success" else st.warning)(f"**{c['verdict']}**  \n{c['sub']}")
            st.markdown("**Why the agent recommends this**")
            for reason, ref in c["why"]:
                st.markdown(f"- {reason}  \n  <small>{ref}</small>", unsafe_allow_html=True)
            if not s["dec"]:
                st.caption("The agent recommends. The credit officer decides and is accountable.")
                b1, b2, b3 = st.columns(3)
                if b1.button("Approve"): s["dec"] = "approve"; st.rerun()
                if b2.button("Refer"): s["dec"] = "refer"; st.rerun()
                if b3.button("Reject"): s["dec"] = "reject"; st.rerun()
            else:
                st.markdown(f"**Officer decision:** {s['dec'].capitalize()}")
                if s["dec"] == "approve" and not s["dis"]:
                    if st.button("Release disbursement", type="primary"): s["dis"] = True; st.rerun()
                if s["dis"]:
                    st.success("Funds released to salary account. Case closed.")
