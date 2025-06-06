# app/management/commands/populate_industries.py
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from mainapps.common.models import TypeOf, ModelChoice  # Replace 'your_app' with your actual app name
from mptt.exceptions import InvalidMove

class Command(BaseCommand):
    help = 'Populates the database with industry categories'

    def handle(self, *args, **kwargs):
        # industry
        # industry_data = {
        #     'Manufacturing': {
        #         'children': {
        #             'Automotive': {
        #                 'children': {
        #                     'Car Manufacturing': {},
        #                     'Auto Parts': {},
        #                     'Commercial Vehicles': {},
        #                 }
        #             },
        #             'Electronics': {
        #                 'children': {
        #                     'Consumer Electronics': {},
        #                     'Industrial Electronics': {},
        #                     'Semiconductors': {},
        #                 }
        #             },
        #             # Add more manufacturing sub-industries
        #         }
        #     },
        #     'Technology': {
        #         'children': {
        #             'Software': {
        #                 'children': {
        #                     'Enterprise Software': {},
        #                     'Mobile Applications': {},
        #                     'AI/Machine Learning': {},
        #                 }
        #             },
        #             'Hardware': {
        #                 'children': {
        #                     'Computer Hardware': {},
        #                     'Networking Equipment': {},
        #                     'IoT Devices': {},
        #                 }
        #             },
        #         }
        #     },
        #     'Healthcare': {
        #         'children': {
        #             'Pharmaceuticals': {},
        #             'Medical Devices': {},
        #             'Healthcare Services': {},
        #         }
        #     },
        #     # Add more parent industries
        #     'Construction': {},
        #     'Retail': {
        #         'children': {
        #             'E-commerce': {},
        #             'Department Stores': {},
        #             'Specialty Retail': {},
        #         }
        #     },
        #     'Financial Services': {
        #         'children': {
        #             'Banking': {},
        #             'Insurance': {},
        #             'Investment Services': {},
        #         }
        #     },
        #     'Energy': {
        #         'children': {
        #             'Oil & Gas': {},
        #             'Renewable Energy': {},
        #             'Utilities': {},
        #         }
        #     },
        # }


        # inventory
        # industry_data = {
        #     'Raw Materials': {
        #         'children': {
        #             'Metals': {},
        #             'Plastics': {},
        #             'Chemicals': {},
        #             'Textiles': {},
        #             'Wood': {},
        #             'Glass': {},
        #             'Paper': {},
        #         }
        #     },
        #     'Work in Progress': {
        #         'children': {
        #             'Subassemblies': {},
        #             'Components': {},
        #             'Modules': {},
        #         }
        #     },
        #     'Finished Goods': {
        #         'children': {
        #             'Consumer Electronics': {},
        #             'Furniture': {},
        #             'Apparel': {},
        #             'Automobiles': {},
        #             'Toys': {},
        #             'Appliances': {},
        #             'Tools': {},
        #         }
        #     },
        #     'Maintenance, Repair, and Operations (MRO)': {
        #         'children': {
        #             'Cleaning Supplies': {},
        #             'Lubricants': {},
        #             'Tools': {},
        #             'Safety Equipment': {},
        #             'Office Supplies': {},
        #         }
        #     },
        #     'Packaging Materials': {
        #         'children': {
        #             'Boxes': {},
        #             'Bags': {},
        #             'Pallets': {},
        #             'Containers': {},
        #             'Labels': {},
        #         }
        #     },
        #     'Safety Stock': {
        #         'children': {
        #             'Emergency Supplies': {},
        #             'Backup Components': {},
        #         }
        #     },
        #     'Consignment Inventory': {
        #         'children': {
        #             'Vendor Managed Inventory': {},
        #             'Third-Party Logistics': {},
        #         }
        #     },
        #     'Pipeline Inventory': {
        #         'children': {
        #             'In-Transit Goods': {},
        #             'Goods Awaiting Inspection': {},
        #         }
        #     },
        #     'Decoupling Inventory': {
        #         'children': {
        #             'Buffer Stock': {},
        #             'Intermediate Goods': {},
        #         }
        #     },
        #     'Anticipation Inventory': {
        #         'children': {
        #             'Seasonal Stock': {},
        #             'Promotional Items': {},
        #         }
        #     },
        #     'Cycle Inventory': {
        #         'children': {
        #             'Regular Stock': {},
        #             'Reorder Level Items': {},
        #         }
        #     },
        #     'Service Inventory': {
        #         'children': {
        #             'Spare Parts': {},
        #             'Replacement Units': {},
        #         }
        #     },
        #     'Perpetual Inventory': {
        #         'children': {
        #             'Automated Replenishment Items': {},
        #             'Continuous Review Stock': {},
        #         }
        #     },
        #     'Periodic Inventory': {
        #         'children': {
        #             'Scheduled Review Items': {},
        #             'Batch Ordered Stock': {},
        #         }
        #     },
        #     'Just-In-Time Inventory': {
        #         'children': {
        #             'On-Demand Stock': {},
        #             'Lean Inventory Items': {},
        #         }
        #     },
        #     'Obsolete Inventory': {
        #         'children': {
        #             'Discontinued Products': {},
        #             'Expired Goods': {},
        #         }
        #     },
        #     'Excess Inventory': {
        #         'children': {
        #             'Overstocked Items': {},
        #             'Slow-Moving Goods': {},
        #         }
        #     },
        #     'Dead Stock': {
        #         'children': {
        #             'Non-Moving Items': {},
        #             'Unsellable Goods': {},
        #         }
        #     },
        #     'Virtual Inventory': {
        #         'children': {
        #             'Digital Products': {},
        #             'E-books': {},
        #             'Software Licenses': {},
        #         }
        #     },
        #     'Drop Shipping Inventory': {
        #         'children': {
        #             'Third-Party Fulfilled Goods': {},
        #             'Direct Shipped Items': {},
        #         }
        #     },
        #     'Cross-Docking Inventory': {
        #         'children': {
        #             'Immediate Transfer Goods': {},
        #             'Direct Distribution Items': {},
        #         }
        #     },
        #     'Reverse Logistics Inventory': {
        #         'children': {
        #             'Returned Goods': {},
        #             'Recyclable Materials': {},
        #         }
        #     },
        #     'Perishable Inventory': {
        #         'children': {
        #             'Fresh Produce': {},
        #             'Dairy Products': {},
        #             'Meat Products': {},
        #             'Baked Goods': {},
        #             'Pharmaceuticals': {},
        #         }
        #     },
        #     'Non-Perishable Inventory': {
        #         'children': {
        #             'Canned Goods': {},
        #             'Dry Foods': {},
        #             'Household Items': {},
        #         }
        #     },
        #     'Hazardous Materials Inventory': {
        #         'children': {
        #             'Flammable Liquids': {},
        #             'Toxic Substances': {},
        #             'Corrosive Materials': {},
        #         }
        #     },
        #     'High-Value Inventory': {
        #         'children': {
        #             'Precious Metals': {},
        #             'Luxury Goods': {},
        #             'Electronics': {},
        #         }
        #     },
        #     'Low-Value Inventory': {
        #         'children': {
        #             'Stationery': {},
        #             'Basic Tools': {},
        #         }
        #     },
        #     'Bulk Inventory': {
        #         'children': {
        #             'Grains': {},
        #             'Liquids': {},
        #             'Chemicals': {},
        #         }
        #     },
        #     'Serialized Inventory': {
        #         'children': {
        #             'Electronics': {},
        #             'Appliances': {},
        #         }
        #     },
        #     'Lot Controlled Inventory': {
        #         'children': {
        #             'Pharmaceuticals': {},
        #             'Food Products': {},
        #         }
        #     },
        #     'Consigned Inventory': {
        #         'children': {
        #             'Vendor Stock': {},
        #             'Third-Party Goods': {},
        #         }
        #     },
        #     'Recyclable Inventory': {
        #         'children': {
        #             'Scrap Metal': {},
        #             'Paper Waste': {},
        #             'Plastic Waste': {},
        #         }
        #     },
        #     'Seasonal Inventory': {
        #         'children': {
        #             'Holiday Decorations': {},
        #             'Winter Apparel': {},
        #             'Summer Gear': {},
        #         }
        #     },
        #     'Promotional Inventory': {
        #         'children': {
        #             'Marketing Materials': {},
        #             'Sample Products': {},
        #         }
        #     },
        #     'Repairable Inventory': {
        #         'children': {
        #             'Refurbished Items': {},
        #             'Reconditioned Goods': {},
        #         }
        #     },
        #     'Service Parts Inventory': {
        #         'children': {
        #             'Replacement Parts': {},
        #             'Spare Components': {},
        #         }
        #     },
        #     'Project Inventory': {
        #         'children': {
        #             'Construction Materials': {},
        #             'Event Supplies': {},
        #         }
        #     },
        #     'Work-In-Process Inventory': {
        #         'children': {
        #             'Partially Assembled Products': {},
        #             'In-Progress Services': {},
        #         }
        #     },
        #     'Finished Goods Inventory': {
        #         'children': {
        #             'Completed Products': {},
        #             'Ready-to-Sell Items': {},
        #         }
        #     },
        #     'Distribution Inventory': {
        #         'children': {
        #             'Wholesale Goods': {},
        #             'Retail Stock': {},
        #         }
        #     },
        #     'Transit Inventory': {
        #         'children': {
        #             'Shipped Goods': {},
        #             'In-Transit Items': {},
        #         }
        #     },
        #     'Buffer Inventory': {
        #         'children': {
        #             'Safety Stock': {},
        #             'Reserve Materials': {},
        #         }
        #     },
        #     'Anticipation Stock': {
        #         'children': {
        #             'Seasonal Goods': {},
        #             'Promotional Items': {},
        #         }
        #     },
        #     'Decoupling Inventory': {
        #         'children': {
        #             'Buffer Stock': {},
        #             'Intermediate Goods': {},
        #         }
        #     },
        #     'Cycle Stock': {
        #         'children': {

        #             'Regular Stock': {},
        #             'Reorder Level Items': {},
        #         }
        #     },
        #     'Service Inventory': {
        #         'children': {
        #             'Spare Parts': {},
        #             'Replacement Units': {},
        #         }
        #     },
        #     'Perpetual Inventory': {
        #         'children': {
        #             'Automated Replenishment Items': {},
        #             'Continuous Review Stock': {},
        #         },
        #     },
        #     'Periodic Inventory': {
        #         'children': {
        #             'Scheduled Review Items': {},
        #             'Batch Ordered Stock': {},
        #         },  
        #     },
        #     'Just-In-Time Inventory': {
        #         'children': {
        #             'On-Demand Stock': {},
        #             'Lean Inventory Items': {},
        #         },  
        #     },
        #     'Obsolete Inventory': {
        #         'children': {
        #             'Discontinued Products': {},
        #             'Expired Goods': {},
        #         }, 
        #     },
        #     'Excess Inventory': {
        #         'children': {
        #             'Overstocked Items': {},
        #             'Slow-Moving Goods': {},
        #         },  
        #     },

        #     }
        
        # stock_item
        industry_data = {
    'Raw Materials': {
        'children': {
            'Metals': {
                'children': {
                    'Steel': {},
                    'Aluminum': {},
                    'Copper': {},
                    'Brass': {},
                    'Titanium': {},
                    'Zinc': {},
                    'Nickel': {},
                    'Lead': {},
                    'Iron': {},
                    'Magnesium': {},
                }
            },
            'Plastics': {
                'children': {
                    'Polyethylene (PE)': {},
                    'Polypropylene (PP)': {},
                    'Polyvinyl Chloride (PVC)': {},
                    'Polystyrene (PS)': {},
                    'Polyethylene Terephthalate (PET)': {},
                    'Acrylonitrile Butadiene Styrene (ABS)': {},
                    'Polytetrafluoroethylene (PTFE)': {},
                    'Polycarbonate (PC)': {},
                    'Polyamide (Nylon)': {},
                    'Polyurethane (PU)': {},
                }
            },
            'Chemicals': {
                'children': {
                    'Acids': {
                        'children': {
                            'Sulfuric Acid': {},
                            'Hydrochloric Acid': {},
                            'Nitric Acid': {},
                            'Acetic Acid': {},
                            'Phosphoric Acid': {},
                        }
                    },
                    'Bases': {
                        'children': {
                            'Sodium Hydroxide': {},
                            'Potassium Hydroxide': {},
                            'Calcium Hydroxide': {},
                            'Ammonium Hydroxide': {},
                        }
                    },
                    'Solvents': {
                        'children': {
                            'Ethanol': {},
                            'Methanol': {},
                            'Acetone': {},
                            'Toluene': {},
                            'Xylene': {},
                        }
                    },
                    'Salts': {
                        'children': {
                            'Sodium Chloride': {},
                            'Potassium Nitrate': {},
                            'Calcium Carbonate': {},
                            'Magnesium Sulfate': {},
                        }
                    },
                }
            },
            'Textiles': {
                'children': {
                    'Cotton': {},
                    'Wool': {},
                    'Silk': {},
                    'Linen': {},
                    'Polyester': {},
                    'Nylon': {},
                    'Rayon': {},
                    'Acrylic': {},
                    'Spandex': {},
                    'Hemp': {},
                }
            },
            'Wood': {
                'children': {
                    'Hardwood': {
                        'children': {
                            'Oak': {},
                            'Maple': {},
                            'Cherry': {},
                            'Walnut': {},
                            'Mahogany': {},
                        }
                    },
                    'Softwood': {
                        'children': {
                            'Pine': {},
                            'Cedar': {},
                            'Spruce': {},
                            'Fir': {},
                            'Redwood': {},
                        }
                    },
                }
            },
            'Glass': {
                'children': {
                    'Float Glass': {},
                    'Tempered Glass': {},
                    'Laminated Glass': {},
                    'Insulated Glass': {},
                    'Colored Glass': {},
                }
            },
            'Paper': {
                'children': {
                    'Kraft Paper': {},
                    'Bond Paper': {},
                    'Coated Paper': {},
                    'Recycled Paper': {},
                    'Cardstock': {},
                }
            },
        }
    },
    'Work in Progress': {
        'children': {
            'Subassemblies': {
                'children': {
                    'Engine Modules': {},
                    'Circuit Boards': {},
                    'Gear Assemblies': {},
                    'Hydraulic Systems': {},
                    'Pneumatic Systems': {},
                }
            },
            'Components': {
                'children': {
                    'Resistors': {},
                    'Capacitors': {},
                    'Transistors': {},
                    'Integrated Circuits': {},
                    'Bearings': {},
                    'Fasteners': {},
                    'Seals': {},
                    'Gaskets': {},
                    'Springs': {},
                    'Valves': {},
                }
            },
            'Modules': {
                'children': {
                    'Power Supply Units': {},
                    'Control Panels': {},
                    'Display Modules': {},
                    'Sensor Modules': {},
                    'Communication Modules': {},
                }
            },
        }
    },
    'Finished Goods': {
        'children': {
            'Consumer Electronics': {
                'children': {
                    'Smartphones': {},
                    'Laptops': {},
                    'Tablets': {},
                    'Televisions': {},
                    'Cameras': {},
                    'Smartwatches': {},
                    'Headphones': {},
                    'Speakers': {},
                    'Game Consoles': {},
                    'Wearable Devices': {},
                }
            },
            'Furniture': {
                'children': {
                    'Sofas': {},
                    'Chairs': {},
                    'Tables': {},
                    'Beds': {},
                    'Cabinets': {},
                    'Desks': {},
                    'Wardrobes': {},
                    'Shelves': {},
                    'Dressers': {},
                    'Benches': {},
                }
            },
            'Apparel': {
                'children': {
                    'Men\'s Clothing': {
                        'children': {
                            'Shirts': {},
                            'Pants': {},
                            'Jackets': {},
                            'Suits': {},
                            'T-Shirts': {},
                        }
                    },
                    'Women\'s Clothing': {
                        'children': {
                            'Dresses': {},
                            'Blouses': {},
                            'Skirts': {},
                            'Tops': {},
                            'Jeans': {},
                        }
                    },
                    'Children\'s Clothing': {
                        'children': {
                            'Onesies': {},
                            'Overalls': {},
                            'School Uniforms': {},
                            'Hoodies': {},
                            'Shorts': {},
                        }
                    },
                }
            },
            'Automobiles': {
                'children': {
                    'Sedans': {},
                    'SUVs': {},
                    'Trucks': {},
                    'Motorcycles': {},
                    'Electric Vehicles': {},
                }
            },
            'Toys': {
                'children': {
                    'Action Figures': {},
                    'Dolls': {},
                    'Board Games': {},
                    'Puzzles': {},
                    'Educational Toys': {},
                    'Building Blocks': {},
                    'Remote Control Toys': {},
                    'Plush Toys': {},
                    'Outdoor Toys': {},
                    'Art and Craft Kits': {},
                }
            },
            'Appliances': {
                'children': {
                    'Refrigerators': {},
                    'Washing Machines': {},
                    'Microwaves': {},
                    'Dishwashers': {},
                    'Air Conditioners': {},
                    'Vacuum Cleaners': {},
                    'Ovens': {},
                    'Toasters': {},
                    'Blenders': {},
                    'Coffee Makers': {},
                }
            },
            'Tools': {
                'children': {
                    'Hand Tools': {
                        'children': {
                            'Hammers': {},
                            'Screwdrivers': {},
                            'Wrenches': {},
                            'Pliers': {},
                            'Chisels': {},
                        }
                    },
                    
                    'Power Tools': {
                        'children': {
                            'Drills': {},
                            'Saws': {},
                            'Sanders': {},
                            'Grinders': {},
                            'Routers': {},
                        }
                    },
                    'Gardening Tools': {
                        'children': {
                            'Pruners': {},
                            'Loppers': {},
                            'Shears': {},
                            'Trowels': {},
                            'Rakes': {},
                        }
                    }, 
                }
            },
        }
    },
    'Maintenance, Repair, and Operations (MRO)': { },
    'Packaging Materials': { },
    'Safety Stock': { },
        }
        
        
        def create_industries(data, parent=None):
            for name, details in data.items():
                try:
                    industry, created = TypeOf.objects.get_or_create(
                        name=name,
                        which_model=ModelChoice.stockitem,
                        defaults={
                            # 'which_model': ModelChoice.inventory,
                            # 'slug': slugify(name),
                            'parent': parent,
                            'description': f"{name} Stock Item Category",
                            'is_active': True
                        }
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS(f'Created industry: {name}'))
                    else:
                        self.stdout.write(self.style.WARNING(f'Industry already exists: {name}'))
                    
                    if 'children' in details:
                        create_industries(details['children'], parent=industry)
                
                except InvalidMove:
                    self.stdout.write(self.style.ERROR(f'Error creating industry: {name}'))
        def delete_industries():
            for industry in TypeOf.objects.filter(which_model=ModelChoice.inventory):
                industry.delete()
                print(f'Deleted industry: ')

            self.stdout.write(self.style.WARNING('Deleted all industries!'))
        self.stdout.write(self.style.WARNING('Starting industry population...'))
        # delete_industries()
        create_industries(industry_data)
        self.stdout.write(self.style.SUCCESS('Successfully populated industries!'))