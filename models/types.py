import enum
import numbers


class BankTypes(enum.Enum):
    TRADITIONAL = "traditional"
    CREDIT_ISSUER = "credit_issuer"
    MORTGAGE_LENDER = "mortgage_lender"

class AccountType(enum.Enum):
    CHECKING = "checking"
    SAVINGS = "savings"
    MORTGAGE = "mortgage"
    MONEY_MARKET = "money_market"
    CD = "cd"
    CASH = "cash"
    PREPAID = "prepaid"
    WALLET = "wallet"
    EBT = "ebt"
    HSA = "hsa"
    FSA = "fsa"
    INVESTMENT = "investment"
    RETIREMENT = "retirement"
    OTHER = "other"


# What each kind of bank account is for and how the planner treats it.
#   group      cash | savings | benefits | invested | other (how it's grouped on screen)
#   pays_bills the planner may pay bills and move money from it
#   earns      its rate is added monthly (interest, or expected growth for investments)
#   purpose    what a restricted balance can be spent on
ACCOUNT_KINDS = {
    "checking": {"label": "Checking", "group": "cash", "pays_bills": True, "earns": False,
                 "hint": "Your everyday account. Bills and Safe to spend come from here."},
    "savings": {"label": "Savings", "group": "savings", "pays_bills": True, "earns": True,
                "hint": "Earns interest. The optimizer can move spare cash here and back."},
    "money_market": {"label": "Money market", "group": "savings", "pays_bills": True, "earns": True,
                     "hint": "Treated like savings."},
    "cd": {"label": "CD", "group": "savings", "pays_bills": False, "earns": True,
           "hint": "Locked until it matures, so it's never used to pay bills."},
    "cash": {"label": "Cash", "group": "cash", "pays_bills": False, "earns": False,
             "hint": "Cash on hand. Counted in your net worth, not used for bills."},
    "prepaid": {"label": "Prepaid card", "group": "cash", "pays_bills": True, "earns": False,
                "hint": "A reloadable card that can pay bills."},
    "wallet": {"label": "PayPal / Venmo / Cash App", "group": "cash", "pays_bills": True, "earns": False,
               "hint": "Money sitting in a payment app."},
    "ebt": {"label": "EBT / SNAP", "group": "benefits", "pays_bills": False, "earns": False, "purpose": "food",
            "hint": "Food benefits. Never counted as spending money or used for bills; "
                    "it can pay for part of your groceries."},
    "hsa": {"label": "HSA", "group": "benefits", "pays_bills": False, "earns": True, "purpose": "medical",
            "hint": "Health savings. Only for medical costs, so it isn't spending money."},
    "fsa": {"label": "FSA", "group": "benefits", "pays_bills": False, "earns": False, "purpose": "medical",
            "hint": "Flexible spending for medical (or dependent care) costs."},
    "investment": {"label": "Brokerage", "group": "invested", "pays_bills": False, "earns": True,
                   "hint": "Investments. The rate is the growth you expect per year."},
    "retirement": {"label": "Retirement", "group": "invested", "pays_bills": False, "earns": True,
                   "hint": "401(k), IRA and similar. The rate is the growth you expect per year."},
    "other": {"label": "Other", "group": "other", "pays_bills": False, "earns": False,
              "hint": "Anything else. Counted in your net worth only."},
}
BANK_ACCOUNT_KINDS = tuple(ACCOUNT_KINDS)
PURPOSE_LABELS = {"food": "Groceries", "medical": "Medical"}


def account_kind(account) -> dict:
    """The ACCOUNT_KINDS entry for a bank account (or a type value)."""
    value = getattr(getattr(account, "account_type", account), "value", getattr(account, "account_type", account))
    return ACCOUNT_KINDS.get(value, ACCOUNT_KINDS["other"])


def pays_bills(account) -> bool:
    return account_kind(account)["pays_bills"]


def is_savings_like(account) -> bool:
    """Savings and money market: where the optimizer parks spare cash."""
    return account_kind(account)["group"] == "savings" and account_kind(account)["pays_bills"]

class CreditAccountStatus(enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    FROZEN = "frozen"

class MortgageStatus(enum.Enum):
    ACTIVE = "active"
    PAID_OFF = "paid_off"
    REFINANCED = "refinanced"
    SOLD = "sold"

class HELOCPhase(enum.Enum):
    DRAW = "draw"          # Can borrow, interest-only minimums
    REPAYMENT = "repayment" # No new draws, amortized payments
    PAID_OFF = "paid_off"

class BillType(enum.Enum):
    FIXED = "fixed"  # Same amount every period
    FLOATING = "floating"  # Variable amount
    CREDIT_PAYMENT = "credit_payment"  # Credit card payment
    MORTGAGE_PAYMENT = "mortgage_payment"  # Mortgage payment
    HELOC_PAYMENT = "heloc_payment"  # HELOC payment
    GROUP_PAYMENT = "group_payment"  # Bill group (bundled loan) payment

class BillFrequency(enum.Enum):
    ONCE = "once"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"  # Every 6 months
    YEARLY = "yearly"

class AllocationMethod(enum.Enum):
    PROPORTIONAL = "proportional"  # Distribute proportional to each sub-loan balance
    FIXED = "fixed"               # User-specified fixed amount per sub-loan
    EQUAL = "equal"               # Split equally across all sub-loans

class DistributionEnumType(enum.Enum):
    FIXED_AMOUNT = "fixed_amount"
    PERCENTAGE = "percentage"
    REMAINDER = "remainder"

class DistributionEntryType(object):
    """Entry for a specific account's distribution."""

    def __init__(self, account_name: str, value: numbers.Number | None, distribution_type: DistributionEnumType):
        """
        Args:
            account_name: Name of the account
            value: Amount, percentage, or "remainder"
        """
        self.account_name = account_name
        self.value = value
        self.distribution_type = distribution_type



class DistributionType(object):
    """Type of distribution for income or payments."""

    def __init__(self, distribution: list[DistributionEntryType]):
        """
        Args:
            distribution: {account_name: amount or "remainder"} or {account_name: percentage}
        """
        self.distribution = distribution

    def add_account_distribution(self, account_name: str, value: numbers.Number | None, distribution_type: DistributionEnumType):
        """Add or update distribution for a specific account."""
        for entry in self.distribution:
            if entry.account_name == account_name:
                entry.value = value
                entry.distribution_type = distribution_type
                return
        self.distribution.append(DistributionEntryType(account_name, value, distribution_type))

    def get_account_distribution_type(self, account_name: str) -> DistributionEntryType | None:
        """Get distribution entry for a specific account."""
        for entry in self.distribution:
            if entry.account_name == account_name:
                return entry
        return None

    def get_distribution_type(self, account_name: str) -> DistributionEnumType | None:
        """Get distribution type for a specific account."""
        entry = self.get_account_distribution_type(account_name)
        if entry:
            return entry.distribution_type
        return None

    def items(self):
        """Return items like a dict for backward compatibility."""
        return self.__todict__().items()

    def keys(self):
        """Return keys like a dict for backward compatibility."""
        return self.__todict__().keys()

    def values(self):
        """Return values like a dict for backward compatibility."""
        return self.__todict__().values()

    def __iter__(self):
        """Allow iteration like a dict."""
        return iter(self.__todict__())

    def __getitem__(self, key):
        """Allow dict-like access."""
        return self.__todict__()[key]

    def __contains__(self, key):
        """Allow 'in' operator like a dict."""
        return key in self.__todict__()

    def __len__(self):
        """Return number of entries."""
        return len(self.distribution)

    def __todict__(self) -> dict:
        """Convert distribution to dictionary format."""
        dist_dict = {}
        for entry in self.distribution:
            dist_dict[entry.account_name] = entry.value
        return dist_dict

    def to_json(self) -> dict:
        """Convert to JSON-serializable format with type information."""
        return {
            entry.account_name: {
                "value": entry.value,
                "type": entry.distribution_type.value
            }
            for entry in self.distribution
        }

    def to_simple_dict(self) -> dict:
        """Convert to simple dict format for JSON serialization."""
        return self.__todict__()

    @classmethod
    def __fromdict__(cls, dist_dict: dict):
        """Load distribution from dictionary format."""
        distribution = []
        if dist_dict is None:
            return None
        for account_name, value in dist_dict.items():
            # Determine type based on value
            if value is None or value == "remainder":
                dist_type = DistributionEnumType.REMAINDER
                val = None
            elif isinstance(value, dict):
                # Full format with type info
                val = value.get("value")
                type_str = value.get("type", "percentage")
                dist_type = DistributionEnumType(type_str)
            elif isinstance(value, (int, float)) and 0 < value <= 1:
                dist_type = DistributionEnumType.PERCENTAGE
                val = value
            else:
                dist_type = DistributionEnumType.FIXED_AMOUNT
                val = value
            distribution.append(DistributionEntryType(account_name, val, dist_type))
        return cls(distribution=distribution)
