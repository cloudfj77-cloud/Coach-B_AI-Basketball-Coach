"""Generate a dependency-free Xcode project from Swift files."""
import hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1]
project=root/'ios/HoopJournal.xcodeproj'
project.mkdir(exist_ok=True)
def ident(name): return hashlib.sha256(name.encode()).hexdigest()[:24].upper()
objects=[]
def obj(name,body):
    objects.append(f'{ident(name)} = {{ {body} }};')
    return ident(name)
files=[]; builds=[]
for source in sorted((root/'ios/HoopJournal').glob('*.swift')):
    f=obj(source.name, f'isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = HoopJournal/{source.name}; sourceTree = "<group>";')
    b=obj(source.name+'-build',f'isa = PBXBuildFile; fileRef = {f};')
    files.append(f);builds.append(b)
app=obj('app','isa = PBXFileReference; explicitFileType = wrapper.application; path = HoopJournal.app; sourceTree = BUILT_PRODUCTS_DIR;')
products=obj('products',f'isa = PBXGroup; children = ({app},); name = Products; sourceTree = "<group>";')
group=obj('group',f'isa = PBXGroup; children = ({",".join(files+[products])},); sourceTree = "<group>";')
sources=obj('sources',f'isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = ({",".join(builds)},); runOnlyForDeploymentPostprocessing = 0;')
frameworks=obj('frameworks','isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0;')
resources=obj('resources','isa = PBXResourcesBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0;')
base='''PRODUCT_NAME = "$(TARGET_NAME)"; PRODUCT_BUNDLE_IDENTIFIER = com.cloud77luke.hoopjournal; SWIFT_VERSION = 5.0; IPHONEOS_DEPLOYMENT_TARGET = 18.0; TARGETED_DEVICE_FAMILY = 1; SDKROOT = iphoneos; SUPPORTED_PLATFORMS = "iphoneos iphonesimulator"; GENERATE_INFOPLIST_FILE = YES; CODE_SIGN_STYLE = Automatic; INFOPLIST_KEY_CFBundleDisplayName = "Coach B"; INFOPLIST_KEY_UILaunchScreen_Generation = YES; INFOPLIST_KEY_UIApplicationSceneManifest_Generation = YES; INFOPLIST_KEY_UISupportedInterfaceOrientations = UIInterfaceOrientationPortrait; INFOPLIST_KEY_NSPhotoLibraryAddUsageDescription = "将你的训练集锦保存到相册，方便分享。"; MARKETING_VERSION = 0.1.0; CURRENT_PROJECT_VERSION = 1; ENABLE_USER_SCRIPT_SANDBOXING = YES;'''
configs=[]
for name in ('Debug','Release'):
    extras='SWIFT_OPTIMIZATION_LEVEL = "-Onone"; SWIFT_ACTIVE_COMPILATION_CONDITIONS = DEBUG; INFOPLIST_KEY_NSAppTransportSecurity_NSAllowsLocalNetworking = YES; INFOPLIST_KEY_NSLocalNetworkUsageDescription = "连接你自己的 Mac，上传训练视频并读取训练记录。";' if name=='Debug' else 'SWIFT_OPTIMIZATION_LEVEL = "-O";'
    configs.append(obj(name,f'isa = XCBuildConfiguration; name = {name}; buildSettings = {{ {base} {extras} }};'))
configlist=obj('configlist',f'isa = XCConfigurationList; buildConfigurations = ({",".join(configs)},); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release;')
target=obj('target',f'isa = PBXNativeTarget; buildConfigurationList = {configlist}; buildPhases = ({sources},{frameworks},{resources},); buildRules = (); dependencies = (); name = HoopJournal; productName = HoopJournal; productReference = {app}; productType = "com.apple.product-type.application";')
projectconfig=[]
for name in ('Debug','Release'):
    projectconfig.append(obj('project'+name,f'isa = XCBuildConfiguration; name = {name}; buildSettings = {{ CLANG_ENABLE_MODULES = YES; }};'))
pcl=obj('projectconfig',f'isa = XCConfigurationList; buildConfigurations = ({",".join(projectconfig)},); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release;')
rootid=obj('project',f'isa = PBXProject; attributes = {{ LastUpgradeCheck = 2700; }}; buildConfigurationList = {pcl}; compatibilityVersion = "Xcode 14.0"; developmentRegion = zh_Hans; hasScannedForEncodings = 0; knownRegions = (en, Base, zh_Hans); mainGroup = {group}; productRefGroup = {products}; projectDirPath = ""; projectRoot = ""; targets = ({target},);')
(project/'project.pbxproj').write_text('// !$*UTF8*$!\n{ archiveVersion = 1; classes = {}; objectVersion = 56; objects = {\n'+'\n'.join(objects)+f'\n}}; rootObject = {rootid}; }}\n')
