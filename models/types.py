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
