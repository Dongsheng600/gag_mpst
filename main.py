'''
Checking protocol, not the program

Compare with strongly acyclic algorithm

Derive Local Types

Prove correctness

'''

safeSorts = set()
safeForms = set()

def is_safe_sort(sort: Sort):
	if(sort in safeSorts):
			return True
	for form in sort.forms:
		if not is_safe_form(form):
			return False
	safeSorts.add(sort)
	return True

def is_safe_form(form: Form):
	if(form in safeForms):
		return True
	# for rule in form.rules:
	# 	if not is_safe_production_rule(rule):
	# 		return False
	# return True
	#! Consider recursive case
	for rule in form.rules:
		if is_safe_production_rule(rule):
			safeForms.add(form)
			return True
	return False

def is_safe_production_rule(rule: Rule):
	if len(rule.children) == 0:
		return True
	for child in rule.children: # These are forms
		if not is_safe_form(child):
			return False
	return True

def is_safe_system(interfaces: list[Form]):
	for interface in interfaces: # These are forms
		if not is_safe_form(interface):
			return False
	return True

def is_safe_gag(gag: GAG):
	changed = True
	while changed:
		init = len(safeForms)
		for sort in gag.sorts:
			is_safe_sort(sort)
		if is_safe_system(gag.interfaces):
			return True
		changed = init == len(safeForms)
	return False
