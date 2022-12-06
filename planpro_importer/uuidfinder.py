def find_infrastructure_element_by_uuid(container, uuid):
    for property in container.__dict__:
        if isinstance(container.__dict__[property], list):
            element_list = container.__dict__[property]
            for element in element_list:
                if element.Identitaet.Wert == uuid:
                    return element
    return None
