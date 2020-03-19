import argparse
import re
import pprint
from yaml import load

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

YARRRML_KEYS = {
    'mappings': ['mappings', 'mapping'],
    'predicateobjects': ['predicateobjects', 'predicateobject', 'po'],
    'predicates': ['predicates', 'predicate', 'p'],
    'objects': ['objects', 'object', 'o'],
    'value': ['value', 'v']
}

IGNORED_PROPERTIES = ['http://www.w3.org/2000/01/rdf-schema#label',' https://schema.org/name', 'http://www.w3.org/2004/02/skos/core#prefLabel']
IGNORED_CLASSES = ['https://schema.org/Thing']

REF_REGEX = re.compile(r'(\$\(.+?\))')


def get_keys(d, key):
    # Get the value of the first key in corresponding YARRRML_KEYS that match a key in d
    if key in YARRRML_KEYS:
        for yarrrml_key in YARRRML_KEYS[key]:
            if yarrrml_key in d:
                return d[key]
    return {}

def get_generic_template(template):
    generic_template = template
    references = {}
    for index, reference in enumerate(REF_REGEX.findall(template), start=1):
        generic_reference = f'$(field{index})'
        generic_template = generic_template.replace(reference, generic_reference)
        references[generic_reference] = reference
    return references, generic_template

def get_classes_properties_references(mapping):
    classes = []
    properties = []
    references = []
    predicate_objects = get_keys(mapping, 'predicateobjects')
    for predicate_object in predicate_objects:
        # for each predicate object (list) in mapping
        if predicate_object[0] == 'a' \
                or predicate_object[0] == 'rdf:type' \
                or predicate_object[0] == 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type':
            classes.append(predicate_object[1])
        else:
            properties.append(predicate_object[0])
            references.append(predicate_object[1])
    return references, classes, properties


def get_mapping_descr(yarrrml):
    datasource = None
    for source_name, source in yarrrml_mapping['sources'].items():
        datasource = source[0]
    return {'classes': get_classes(yarrrml),
            'properties': get_properties(yarrrml),
            'datasets': datasource,
            'templates': get_templates(yarrrml)}


def get_templates(yarrrml):
    template_list = {'templates': {}}
    # get  yarrrml key of the yarrrml file
    mappings = get_keys(yarrrml, 'mappings')
    for mapping_name, mapping in mappings.items():
        # for each mapping
                references, classes, properties = get_classes_properties_references(mapping)
                references, generic_template = get_generic_template(mapping['subject'])
                template_list['templates'][generic_template] = {
                    'classes': classes,  # classes associated to this template (if subject)
                    'properties': properties,  # properties associated to this template
                    'position': 'S',  # S or O
                    'references': references}

    return template_list


def get_classes(yarrrml):
    classes_list = {'classes': {}}
    # get  yarrrml key of the yarrrml file
    mappings = get_keys(yarrrml, 'mappings')
    for mapping_name, mapping in mappings.items():
        references, classes, properties = get_classes_properties_references(mapping)
        references, generic_template = get_generic_template(mapping['subject'])
        for i in range(len(classes)):
            classes_list['classes'][classes[i]] = {
                # classes associated to this template (if subject)
                'properties': properties,  # properties associated to this template
                'templates': generic_template
                }
    return classes_list


def get_properties(yarrrml):
    properties_list = {'properties': {}}
    # get  yarrrml key of the yarrrml file
    mappings = get_keys(yarrrml, 'mappings')
    for mapping_name, mapping in mappings.items():
        references, classes, properties = get_classes_properties_references(mapping)
        references1, generic_template = get_generic_template(mapping['subject'])
        for i in range(len(properties)):
            properties_list['properties'][properties[i]] = {
                # classes associated to this template (if subject)
                'classes': classes,  # properties associated to this template
                'templates': generic_template,
                'references_templates':references1,
                'references': references[i]
            }

    return properties_list


def mapping_compare(yarrrml_map1, yarrrml_map2):
    common_classes = []
    common_properties = []
    common_templates= []
    datasource = []
    mapping_desc1 = get_mapping_descr(yarrrml_map1)
    mapping_desc2 = get_mapping_descr(yarrrml_map2)
    datasource.append(mapping_desc1['datasets'])
    datasource.append(mapping_desc2['datasets'])
    for classes2 in mapping_desc2['classes']['classes']:
        if classes2 in mapping_desc1['classes']['classes'] and classes2 not in IGNORED_CLASSES:
            common_classes.append(classes2)
    for properties2 in mapping_desc2['properties']['properties']:
        if properties2 in mapping_desc1['properties']['properties'] and properties2 not in IGNORED_PROPERTIES:
            common_properties.append(properties2)
    for templates2 in mapping_desc2['templates']['templates']:
        if templates2 in mapping_desc1['templates']['templates']:
            common_templates.append(templates2)


    return {'templates': common_templates,
            'classes': common_classes,
            'properties': common_properties,
            'datasets': datasource

            }


def basic_graph_patterns(yarrrml1,yarrrml2):
    mapping_comp = mapping_compare(yarrrml1, yarrrml2)
    joins_subject_object = []
    join_subject_predicat_subject_predicat = []
    join_subject_subject= []
    join_object_object= []
    join_predicat_object_predicat_object = []
    join_subject_predicat_predicat_object= []

    for object in mapping_comp['classes']:
        join_object_object.append('?S' + '   ' + '?P' + '  ' + object)
    for subject in mapping_comp['templates']:
         join_subject_subject.append(subject + '   ' + '?P' + '  ' + '?O')
    for template in mapping_comp['templates']:
        if template in mapping_comp['classes'] and template not in IGNORED_CLASSES:
            joins_subject_object.append(template + '   ' + '?P' + '  ' + '?O')
            joins_subject_object.append('?S' + '   ' + '?P' + '  ' + template)
    for templates, objects in (get_templates(yarrrml1)['templates']).items():
        if templates in mapping_compare(yarrrml1, yarrrml2)['templates']:
            for propertie in mapping_compare(yarrrml1, yarrrml2)['properties']:
                if propertie in objects['properties']:
                    join_subject_predicat_subject_predicat.append(templates + '  ' + propertie + '  ' + '?O')
    for properties, object in (get_properties(yarrrml1)['properties']).items():
        for properties1, object1 in (get_properties(yarrrml2)['properties']).items():
            if object['references'] == object1['references'] and properties == properties1:
                join_predicat_object_predicat_object.append('?S' + '  ' + properties + '  ' + object['references'])
    for properties, objects in (get_properties(yarrrml1)['properties']).items():
        for properties1, objects1 in (get_properties(yarrrml2)['properties']).items():
            if properties == properties1 :
                if objects['references'] == objects1['templates'] or objects['templates']   == objects1['references']:
                    join_subject_predicat_predicat_object.append('?S'+'  '+properties+'  '+objects1['references'])
                    join_subject_predicat_predicat_object.append(objects['templates'] +'  '+properties+'  '+'?O')




    return {'subject-subject': join_subject_subject,
            'subject,predicat-subject,predicat': join_subject_predicat_subject_predicat,
            'object-object': join_object_object,
           'predicat_object_predicat_object':join_predicat_object_predicat_object,
            'subject-object': joins_subject_object,
            'subject_predicat_predicat_object':join_subject_predicat_predicat_object}

parser = argparse.ArgumentParser(description='Find federated queries for a federation.')
parser.add_argument('mapping', type=str, help='yarrrml mapping filepath')
parser.add_argument('mapping2', type=str, help='yarrrml mapping filepath')

args = parser.parse_args()

# open yarrrml file
stream = open(args.mapping)
stream2 = open(args.mapping2)

# loading the text file
yarrrml_mapping = load(stream, Loader=Loader)
yarrrml_mapping2 = load(stream2, Loader=Loader)
# method test
pp = pprint.PrettyPrinter(indent=4)
#pp.pprint(mapping_compare(yarrrml_mapping, yarrrml_mapping2))

print(basic_graph_patterns(yarrrml_mapping,yarrrml_mapping2))

