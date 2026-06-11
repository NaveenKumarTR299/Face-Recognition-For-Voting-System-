public class AtmTransaction {
    private double balance;

    // Constructor
    public AtmTransaction(double balance) {
        this.balance = balance;
    }

    // Deposit method
    public void deposit(double amount) {
        try {
            System.out.println("Depositing: " + amount);

            if (amount <= 0) {
                throw new ArithmeticException("Invalid deposit amount");
            }

            balance += amount;
            System.out.println("Deposit successful");
            System.out.println("Balance: " + balance);

        } catch (ArithmeticException e) {
            System.out.println("Deposit error: " + e.getMessage());
        } finally {
            System.out.println("Deposit process completed");
            System.out.println("----------------------");
        }
    }

    // Withdraw method
    public void withdraw(double amount) {
        try {
            System.out.println("Withdrawing: " + amount);

            double fee = amount * 0.02;
            double total = amount + fee;

            if (total > balance) {
                throw new ArithmeticException("Insufficient balance");
            }

            balance -= total;

            System.out.println("Withdrawal successful");
            System.out.println("Fee: " + fee);
            System.out.println("Balance: " + balance);

        } catch (ArithmeticException e) {
            System.out.println("Withdraw error: " + e.getMessage());
        } catch (Exception e) {
            System.out.println("Withdraw error");
        } finally {
            System.out.println("Completed");
            System.out.println("----------------------");
        }
    }

    // Main method (outside withdraw)
    public static void main(String[] args) {
        AtmTransaction atm = new AtmTransaction(1000);

        atm.deposit(500);
        atm.deposit(0);       // error case
        atm.withdraw(300);
        atm.withdraw(2000);   // error case
    }
}