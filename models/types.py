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

class BillType(enum.Enum):
    FIXED = "fixed"  # Same amount every period
    FLOATING = "floating"  # Variable amount
    CREDIT_PAYMENT = "credit_payment"  # Credit card payment
    MORTGAGE_PAYMENT = "mortgage_payment"  # Mortgage payment

class BillFrequency(enum.Enum):
    ONCE = "once"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"  # Every 6 months
    YEARLY = "yearly"

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
    def __todict__(self) -> dict:
        """Convert distribution to dictionary format."""
        dist_dict = {}
        for entry in self.distribution:
            dist_dict[entry.account_name] = entry.value
        return dist_dict

    @classmethod
    def __fromdict__(cls, dist_dict: dict):
        """Load distribution from dictionary format."""
        distribution = []
        if dist_dict is None:
            return None
        for account_name, value, distribution_type in dist_dict.items():
            if distribution_type in DistributionEnumType.__members__:
                distribution_type = DistributionEnumType[distribution_type]
            else:
                raise ValueError(f"Invalid distribution type for account '{account_name}': {value}: {distribution_type}")
            distribution.append(DistributionEntryType(account_name, value, distribution_type))
        return cls(distribution=distribution)
