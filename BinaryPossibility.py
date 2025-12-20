import itertools

class BinaryPossibility:
    """
    This class represents a single binary possibility with a state (0, 1, or None for superposition).
    """

    def __init__(self, state=None):
        if state not in (0, 1, None):
            raise ValueError("Invalid state. Must be 0, 1, or None.")
        self.state = state

    def set_state(self, state):
        if state not in (0, 1, None):
            raise ValueError("Invalid state. Must be 0, 1, or None.")
        self.state = state

    def is_superposition(self):
        return self.state is None

    def __str__(self):
        if self.state is None:
            return "Possibility: (0 & 1)"  # Indicate superposition
        else:
            return f"Possibility: {self.state}"


class BinaryRegister:
    """
    This class represents a register of binary possibilities for storing binary data with superposition.
    """

    def __init__(self, num_bits):
        if num_bits <= 0:
            raise ValueError("Number of bits must be positive.")
        self.possibilities = [BinaryPossibility() for _ in range(num_bits)]

    def add_bit(self):
        self.possibilities.append(BinaryPossibility())

    def remove_bit(self):
        if len(self.possibilities) == 0:
            raise IndexError("Cannot remove bit from empty register.")
        self.possibilities.pop()

    def set_bit(self, index, state):
        if index not in range(len(self.possibilities)):
            raise IndexError("Invalid bit index.")
        if state not in (0, 1, None):
            raise ValueError("Invalid state. Must be 0, 1, or None.")
        self.possibilities[index].set_state(state)

    def get_bit(self, index):
        if index not in range(len(self.possibilities)):
            raise IndexError("Invalid bit index.")
        return self.possibilities[index].state

    def calculate_possibility_count(self):
        """
        Mathematically calculates the total number of possible states without iterating.
        Formula: 2 ^ (number of bits in superposition).
        """
        if len(self.possibilities) == 0:
            return 0
        
        # Count bits in superposition (state is None)
        superposition_count = sum(1 for bit in self.possibilities if bit.is_superposition())
        
        return 2 ** superposition_count

    def enumerate_states(self):
        if len(self.possibilities) == 0:
            return []
        states = []

        def generate_states(i, partial_state):
            if i == len(self.possibilities):
                states.append(partial_state)
                return
            if self.possibilities[i].is_superposition():
                generate_states(i + 1, partial_state + "0")
                generate_states(i + 1, partial_state + "1")
            else:
                state_str = "0" if self.possibilities[i].state == 0 else "1"
                generate_states(i + 1, partial_state + state_str)

        generate_states(0, "")
        return states

    def get_individual_states(self):
        return self.possibilities.copy()


class BinaryRegisterGroup:
    """
    Manages multiple BinaryRegister objects as a unified system.
    """

    def __init__(self, *registers):
        self.registers = registers

    def calculate_possibility_count(self):
        """
        Mathematically calculates the total possibilities of the combined registers.
        """
        total_possibilities = 1
        for reg in self.registers:
            total_possibilities *= reg.calculate_possibility_count()
        return total_possibilities

    def enumerate_states(self):
        """
        Enumerates all combined states by creating the Cartesian product 
        of the individual register states.
        """
        all_state_lists = [reg.enumerate_states() for reg in self.registers]
        combined_iterator = itertools.product(*all_state_lists)
        return ["".join(combination) for combination in combined_iterator]

    def add_register(self, register):
        self.registers = self.registers + (register,)