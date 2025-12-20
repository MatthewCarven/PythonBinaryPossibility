from BinaryPossibility import BinaryRegister,BinaryRegisterGroup
# Example usage
br = BinaryRegister(3)
print("1,None,None")
br.set_bit(0,1)
bre = br.enumerate_states()
for each in bre:
    print(str(each))

print("1,1,None")
br.set_bit(1,1)
bre = br.enumerate_states()
for each in bre:
    print(str(each))

print("None,None,None")
br.set_bit(0,None)
br.set_bit(1,None)
bre = br.enumerate_states()
for each in bre:
    print(str(each))



# 1. Create two registers
reg_a = BinaryRegister(2) # 2 bits
reg_b = BinaryRegister(3) # 3 bits

# 2. Create the group
group = BinaryRegisterGroup(reg_a, reg_b)

# 3. Check the mathematical count (Immediate result, no iteration)
# Initially: 2 bits (4 states) * 3 bits (8 states) = 32 possibilities
print(f"Total Possibilities: {group.calculate_possibility_count()}") 

# 4. Collapse a bit in one register to reduce possibilities
reg_a.set_bit(0, 1) # Set index 0 of Reg A to '1'
# Now: Reg A has 1 superpos bit (2 states) * Reg B (8 states) = 16 possibilities
print(f"New Total: {group.calculate_possibility_count()}")

print(str(group.enumerate_states()))


